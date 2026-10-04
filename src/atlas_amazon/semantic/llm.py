"""LLM-backed semantic providers (live, replayed or scripted, depending on the transport).

`LLMJudgmentProvider` implements the `JudgmentProvider` contract with **one
call per judgment** (the v0.4b path, kept for comparison and for callers that
want it); the v0.5 default is `batched.BatchedJudgmentProvider`, which
batches, caches per judgment and escalates selectively. `LLMReviewThemeProvider`
implements `ReviewThemeProvider` (one call per review set, on the strong tier
by default, with an output budget sized to the number of reviews). Both
providers here use the same call path for every request:

1. **Cache lookup** by (kind, input hash, provider, model, prompt version),
   which must also match the prompt fingerprint.
2. **Budget check** (`UsageLedger.authorize`) before any live call. A refusal
   stops the batch.
3. **Transport** send (live, replay or scripted).
4. **Audit record**: the full request and normalized response are emitted
   as `semantic_call` Evidence (timestamped with the original response
   time), valid or not.
5. **Validation**: the structured output goes through the *existing*
   validators (`judgment_evidence` / `parse_judgment`,
   `review_theme_evidence`). Refusals, truncated or non-JSON output, and
   schema or range violations produce no judgment. They are recorded as
   failures in the usage ledger.
6. Only validated exchanges are cached.

The judgment Evidence content is identical whether it came from a live call,
the cache or a replay, so its content-addressed ID is too. A replay of a
recorded run reproduces the original evidence exactly.

Requests are built from the versioned templates in `semantic/prompts/`,
with structured output (`output_config.format` JSON schema). With
`refusal_fallbacks=True` (the default), requests use the API's server-side
fallback (`fallbacks: "default"`). The served model is recorded separately
from the requested one.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from atlas_amazon.evidence.identity import make_evidence
from atlas_amazon.jsonvalue import canonical_json, thaw
from atlas_amazon.judgments.contract import (
    JudgmentError,
    JudgmentRequest,
    JudgmentType,
    judgment_evidence,
    parse_judgment,
)
from atlas_amazon.models import Evidence, EvidenceKind
from atlas_amazon.reviews.themes import ReviewThemeError, review_theme_evidence
from atlas_amazon.semantic.budgets import expected_themes_output, themes_output_budget
from atlas_amazon.semantic.cache import CacheKey, SemanticCache
from atlas_amazon.semantic.plan import PlannedCall, SemanticCallPlan
from atlas_amazon.semantic.prompts import REVIEW_THEMES, PromptTemplate, load_template
from atlas_amazon.semantic.records import ensure_no_secrets
from atlas_amazon.semantic.tiers import FAST, LLMSettings, ModelTier, ModelTiers
from atlas_amazon.semantic.transport import (
    DEFAULT_FALLBACK_BETA,
    LiveCallsDisabled,
    ReplayMiss,
    Transport,
    TransportResponse,
    request_hash,
)
from atlas_amazon.semantic.usage import (
    BudgetExceeded,
    UsageLedger,
    UsageRecord,
    estimate_tokens,
)

DEFAULT_MODEL = FAST.model


def build_request(
    settings: LLMSettings, template: PromptTemplate, input_data: Any, *, max_tokens: int
) -> dict[str, Any]:
    """A Messages API request for one template rendering. Never holds credentials."""
    output_config: dict[str, Any] = {"format": {"type": "json_schema", "schema": template.schema}}
    if settings.effort is not None:
        output_config["effort"] = settings.effort
    request: dict[str, Any] = {
        "model": settings.model,
        "max_tokens": max_tokens,
        "system": template.system,
        "messages": [{"role": "user", "content": template.render_user(thaw(input_data))}],
        "output_config": output_config,
    }
    if settings.thinking is not None:
        request["thinking"] = thaw(settings.thinking)
    if settings.refusal_fallbacks:
        request["betas"] = [DEFAULT_FALLBACK_BETA]
        request["fallbacks"] = "default"
    ensure_no_secrets(request, "semantic request")
    return request


class MalformedResponse(ValueError):
    pass


@dataclass
class _Exchange:
    request: dict[str, Any]
    response: TransportResponse
    source: str  # "live" | "replay" | "cache"


@dataclass
class _SemanticCaller:
    name: str
    transport: Transport
    settings: LLMSettings
    ledger: UsageLedger
    cache: SemanticCache | None
    failures: list[tuple[str, str]] = field(default_factory=list)  # (purpose:hash, reason)
    tier: str | None = None  # recorded on usage records

    def build_request(
        self, template: PromptTemplate, input_data: Any, max_tokens: int | None = None
    ) -> dict[str, Any]:
        if max_tokens is None:
            max_tokens = template.max_tokens + self.settings.thinking_allowance
        return build_request(self.settings, template, input_data, max_tokens=max_tokens)

    def call_evidence(
        self,
        *,
        purpose: str,
        template: PromptTemplate,
        input_hash: str,
        exchange: _Exchange,
        marketplace: str,
        run_id: str | None,
    ) -> Evidence:
        response = exchange.response
        payload = {
            "purpose": purpose,
            "prompt": {
                "name": template.name,
                "version": template.version,
                "fingerprint": template.fingerprint,
            },
            "input_hash": input_hash,
            "request_hash": request_hash(exchange.request),
            "request": exchange.request,
            "response": response.to_dict(),
        }
        ensure_no_secrets(payload, "semantic_call evidence")
        return make_evidence(
            provider=self.name,
            kind=EvidenceKind.SEMANTIC_CALL,
            marketplace=marketplace,
            retrieved_at=datetime.fromisoformat(response.responded_at),
            payload=payload,
            subject=f"{purpose}:{input_hash}",
            run_id=run_id,
        )

    def exchange(
        self,
        *,
        kind: str,
        input_hash: str,
        template: PromptTemplate,
        input_data: Any,
        purpose: str,
        run_id: str | None,
        max_tokens: int | None = None,
    ) -> _Exchange | None:
        """Cache -> budget -> transport. Raises BudgetExceeded / LiveCallsDisabled to stop."""
        key = CacheKey(kind, input_hash, self.name, self.settings.model, template.version)
        if self.cache is not None:
            found = self.cache.lookup(key, template.fingerprint)
            if found.entry is not None:
                return _Exchange(
                    found.entry["request"],
                    TransportResponse.from_dict(found.entry["response"]),
                    "cache",
                )
        request = self.build_request(template, input_data, max_tokens)
        if self.transport.is_live:
            try:
                self.ledger.authorize(run_id=run_id, model=self.settings.model, request=request)
            except BudgetExceeded as exc:
                self._record(
                    run_id,
                    self.settings.model,
                    purpose,
                    template,
                    "skipped",
                    "budget",
                    detail=exc.reason,
                )
                raise
        source = "live" if self.transport.is_live else "replay"
        try:
            response = self.transport.send(request)
        except ReplayMiss as exc:
            self._record(
                run_id,
                self.settings.model,
                purpose,
                template,
                source,
                "replay_miss",
                detail=str(exc),
            )
            self.failures.append((f"{purpose}:{input_hash}", "replay_miss"))
            return None
        except LiveCallsDisabled:
            raise
        except Exception as exc:  # API/network errors: record and continue without a verdict
            self._record(
                run_id,
                self.settings.model,
                purpose,
                template,
                source,
                "error",
                detail=type(exc).__name__,
            )
            self.failures.append((f"{purpose}:{input_hash}", type(exc).__name__))
            return None
        return _Exchange(request, response, source)

    def finish(
        self,
        *,
        exchange: _Exchange,
        kind: str,
        input_hash: str,
        template: PromptTemplate,
        purpose: str,
        run_id: str | None,
        validate: Callable[[dict[str, Any]], Any],
    ) -> Any | None:
        """Validate the structured output; record usage; cache validated results."""
        response = exchange.response
        outcome, detail, value = "ok", "", None
        if response.stop_reason == "refusal":
            outcome, detail = "refusal", "model declined"
        else:
            try:
                if not response.text:
                    raise MalformedResponse("no text block")
                try:
                    structured = json.loads(response.text)
                except json.JSONDecodeError as exc:
                    raise MalformedResponse(f"not JSON ({response.stop_reason})") from exc
                if not isinstance(structured, dict):
                    raise MalformedResponse("structured output is not an object")
                value = validate(structured)
            except (
                MalformedResponse,
                JudgmentError,
                ReviewThemeError,
                ValueError,
                KeyError,
                TypeError,
            ) as exc:
                outcome, detail, value = "malformed", f"{type(exc).__name__}: {exc}", None
        if outcome != "ok":
            self.failures.append((f"{purpose}:{input_hash}", outcome))
        usage = response.usage if exchange.source != "cache" else {}
        self._record(
            run_id,
            response.model,
            purpose,
            template,
            exchange.source,
            outcome,
            usage=usage,
            detail=detail,
            cost=self.ledger.cost_of(response.model, usage) if exchange.source == "live" else 0.0,
            judgments=1 if outcome == "ok" and kind != REVIEW_THEMES else 0,
        )
        if outcome == "ok" and self.cache is not None and exchange.source != "cache":
            key = CacheKey(kind, input_hash, self.name, self.settings.model, template.version)
            self.cache.put(
                key,
                template.fingerprint,
                {"request": exchange.request, "response": response.to_dict()},
            )
        return value

    def _record(
        self,
        run_id,
        model,
        purpose,
        template,
        source,
        outcome,
        *,
        usage=None,
        detail="",
        cost=None,
        judgments=0,
    ) -> None:
        usage = usage or {}
        self.ledger.record(
            UsageRecord(
                run_id=run_id,
                provider=self.name,
                model=model,
                purpose=purpose,
                prompt_version=template.version,
                source=source,
                outcome=outcome,
                input_tokens=usage.get("input_tokens"),
                output_tokens=usage.get("output_tokens"),
                cache_read_tokens=usage.get("cache_read_input_tokens"),
                cache_write_tokens=usage.get("cache_creation_input_tokens"),
                estimated_cost_usd=cost
                if source == "live"
                else (0.0 if source == "cache" else None),
                detail=detail,
                judgments=judgments,
                tier=self.tier,
            )
        )


def _call_meta(exchange: _Exchange, call_evidence_id: str, requested_model: str) -> dict:
    r = exchange.response
    return {
        "call_evidence_id": call_evidence_id,
        "request_hash": request_hash(exchange.request),
        "response_id": r.id,
        "requested_model": requested_model,
        "served_model": r.model,
        "stop_reason": r.stop_reason,
        "usage": thaw(r.usage),
        "synthetic": r.synthetic,
    }


class LLMJudgmentProvider:
    """`JudgmentProvider` backed by an LLM transport (live, replay or scripted)."""

    def __init__(
        self,
        transport: Transport,
        *,
        settings: LLMSettings | None = None,
        ledger: UsageLedger | None = None,
        cache: SemanticCache | None = None,
        name: str = "anthropic",
    ) -> None:
        self.name = name
        self.settings = settings or LLMSettings()
        self.usage = ledger or UsageLedger()
        self.templates = {t.value: load_template(t.value) for t in JudgmentType}
        self._caller = _SemanticCaller(name, transport, self.settings, self.usage, cache)

    @property
    def failures(self) -> list[tuple[str, str]]:
        return self._caller.failures

    def judge(
        self, requests: Sequence[JudgmentRequest], *, marketplace: str, run_id: str | None = None
    ) -> list[Evidence]:
        out: list[Evidence] = []
        seen: set[str] = set()
        for request in requests:
            if request.input_hash in seen:
                continue
            seen.add(request.input_hash)
            kind = request.type.value
            template = self.templates[kind]
            purpose = f"judgment:{kind}"
            try:
                exchange = self._caller.exchange(
                    kind=kind,
                    input_hash=request.input_hash,
                    template=template,
                    input_data=request.input,
                    purpose=purpose,
                    run_id=run_id,
                )
            except (BudgetExceeded, LiveCallsDisabled):
                break  # fail safe: no further calls in this batch
            if exchange is None:
                continue
            call = self._caller.call_evidence(
                purpose=purpose,
                template=template,
                input_hash=request.input_hash,
                exchange=exchange,
                marketplace=marketplace,
                run_id=run_id,
            )
            out.append(call)
            meta = _call_meta(exchange, call.id, self.settings.model)

            def validate(
                structured: dict[str, Any],
                request=request,
                template=template,
                exchange=exchange,
                meta=meta,
                call=call,
            ) -> Evidence:
                data = dict(structured)
                confidence = data.pop("confidence")
                rationale = data.pop("rationale")
                if request.type is JudgmentType.ENTITY:
                    data["entity"] = data.get("entity") or None
                evidence = judgment_evidence(
                    provider=self.name,
                    request=request,
                    result=data,
                    confidence=confidence,
                    model=exchange.response.model,
                    prompt_version=template.version,
                    rationale=rationale,
                    marketplace=marketplace,
                    judged_at=datetime.fromisoformat(exchange.response.responded_at),
                    run_id=run_id,
                    source_url=f"semantic-call://{call.id}",
                    call=meta,
                )
                parse_judgment(evidence)  # the same parser the run uses; never bypassed
                return evidence

            evidence = self._caller.finish(
                exchange=exchange,
                kind=kind,
                input_hash=request.input_hash,
                template=template,
                purpose=purpose,
                run_id=run_id,
                validate=validate,
            )
            if evidence is not None:
                out.append(evidence)
        return out


def _input_hash(data: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(data).encode("utf-8")).hexdigest()


def review_input(reviews: Sequence[Evidence]) -> tuple[dict[str, Any], dict[str, Evidence]]:
    """Deterministic prompt input for a set of stored reviews, plus ref -> evidence."""
    ordered = sorted(
        (r for r in reviews if r.kind == EvidenceKind.REVIEW_SAMPLE), key=lambda r: r.id
    )
    refs = {f"R{i}": r for i, r in enumerate(ordered, 1)}
    data = {
        "reviews": [
            {
                "ref": ref,
                "asin": r.payload.get("asin", r.subject),
                "rating": r.payload.get("rating"),
                "text": r.payload.get("text"),
            }
            for ref, r in refs.items()
        ]
    }
    return data, refs


class LLMReviewThemeProvider:
    """`ReviewThemeProvider` backed by an LLM transport.

    The model sees only the review evidence passed in (stored in the run),
    referenced as R1..Rn. It returns themes citing refs. Unknown refs are
    dropped, and a theme left with no valid reviews is discarded. Counts and
    products are always recomputed by `review_theme_evidence` from the cited
    review evidence, never taken from the model. The model receives no
    product information, so it has nothing to make claims about our product
    from. Opportunities and first-party support are decided later and
    deterministically by `summarize_review_themes`.
    """

    def __init__(
        self,
        transport: Transport,
        *,
        settings: LLMSettings | None = None,
        ledger: UsageLedger | None = None,
        cache: SemanticCache | None = None,
        name: str = "anthropic",
        tier: ModelTier | str = ModelTier.STRONG,
    ) -> None:
        self.name = name
        self.tier = ModelTier(tier)
        self.settings = settings or ModelTiers()[self.tier]
        self.usage = ledger or UsageLedger()
        self.template = load_template(REVIEW_THEMES)
        self._caller = _SemanticCaller(
            name, transport, self.settings, self.usage, cache, tier=self.tier.value
        )
        self.dropped: list[str] = []  # human-readable notes on discarded refs/themes
        self.plans: list[tuple[str | None, SemanticCallPlan]] = []

    @property
    def failures(self) -> list[tuple[str, str]]:
        return self._caller.failures

    def max_tokens_for(self, review_count: int) -> int:
        """Output budget for `review_count` reviews, never above the template cap."""
        budget = themes_output_budget(review_count)
        return min(self.template.max_tokens, budget) + self.settings.thinking_allowance

    def plans_for(self, run_id: str | None) -> tuple[SemanticCallPlan, ...]:
        return tuple(p for rid, p in self.plans if rid == run_id)

    def plan(
        self, reviews: Sequence[Evidence], *, marketplace: str = "", run_id: str | None = None
    ) -> SemanticCallPlan:
        """The single review-theme call `themes(reviews)` would make. Makes no call."""
        data, refs = review_input(reviews)
        if not refs:
            return SemanticCallPlan(stage=REVIEW_THEMES, provider=self.name, requested=0)
        input_hash = _input_hash(data)
        key = CacheKey(
            REVIEW_THEMES, input_hash, self.name, self.settings.model, self.template.version
        )
        if self._caller.cache is not None and (
            self._caller.cache.lookup(key, self.template.fingerprint).entry is not None
        ):
            return SemanticCallPlan(
                stage=REVIEW_THEMES,
                provider=self.name,
                requested=1,
                cache_hits=1,
                pricing_as_of=self.usage.pricing.as_of,
            )
        request = self._caller.build_request(self.template, data, self.max_tokens_for(len(refs)))
        input_tokens = estimate_tokens(request)
        expected_out = expected_themes_output(len(refs)) + self.settings.thinking_allowance // 4
        price = self.usage.pricing.get(self.settings.model)
        call = PlannedCall(
            tier=self.tier.value,
            model=self.settings.model,
            items=1,
            types={REVIEW_THEMES: 1},
            max_tokens=request["max_tokens"],
            input_tokens=input_tokens,
            expected_output_tokens=expected_out,
            expected_cost_usd=None if price is None else price.cost(input_tokens, expected_out),
            worst_case_cost_usd=None
            if price is None
            else price.cost(input_tokens, request["max_tokens"]),
            request_hash=request_hash(request),
        )
        return SemanticCallPlan(
            stage=REVIEW_THEMES,
            provider=self.name,
            requested=1,
            live=1,
            batches=(call,),
            pricing_as_of=self.usage.pricing.as_of,
            notes=(f"{len(refs)} reviews in one call",),
        )

    def themes(
        self, reviews: Sequence[Evidence], *, marketplace: str, run_id: str | None = None
    ) -> list[Evidence]:
        data, refs = review_input(reviews)
        if not refs:
            return []
        self.plans.append((run_id, self.plan(reviews, marketplace=marketplace, run_id=run_id)))
        input_hash = _input_hash(data)
        purpose = REVIEW_THEMES
        try:
            exchange = self._caller.exchange(
                kind=REVIEW_THEMES,
                input_hash=input_hash,
                template=self.template,
                input_data=data,
                purpose=purpose,
                run_id=run_id,
                max_tokens=self.max_tokens_for(len(refs)),
            )
        except (BudgetExceeded, LiveCallsDisabled):
            return []
        if exchange is None:
            return []
        call = self._caller.call_evidence(
            purpose=purpose,
            template=self.template,
            input_hash=input_hash,
            exchange=exchange,
            marketplace=marketplace,
            run_id=run_id,
        )

        def validate(structured: dict[str, Any]) -> list[Evidence]:
            if set(structured) != {"themes"} or not isinstance(structured["themes"], list):
                raise MalformedResponse("expected {'themes': [...]}")
            built = []
            for i, item in enumerate(structured["themes"]):
                if not isinstance(item, dict):
                    self.dropped.append(f"theme {i}: not an object")
                    continue
                cited = [str(x) for x in item.get("review_refs", ())]
                unknown = [x for x in cited if x not in refs]
                if unknown:
                    self.dropped.append(f"theme {item.get('theme')!r}: unknown refs {unknown}")
                supporting = [refs[x] for x in dict.fromkeys(cited) if x in refs]
                if not supporting:
                    self.dropped.append(f"theme {item.get('theme')!r}: no valid supporting review")
                    continue
                try:
                    built.append(
                        review_theme_evidence(
                            provider=self.name,
                            theme=str(item["theme"]),
                            polarity=item["polarity"],
                            reviews=supporting,
                            terms=[str(t) for t in item.get("terms", ())],
                            extractor=exchange.response.model,
                            extractor_version=self.template.version,
                            rationale=str(item.get("rationale") or ""),
                            marketplace=marketplace,
                            run_id=run_id,
                            extracted_at=datetime.fromisoformat(exchange.response.responded_at),
                            source_url=f"semantic-call://{call.id}",
                        )
                    )
                except (ReviewThemeError, ValueError, KeyError) as exc:
                    self.dropped.append(f"theme {item.get('theme')!r}: {exc}")
            return built

        themes = self._caller.finish(
            exchange=exchange,
            kind=REVIEW_THEMES,
            input_hash=input_hash,
            template=self.template,
            purpose=purpose,
            run_id=run_id,
            validate=validate,
        )
        return [call, *(themes or [])]


Responder = Callable[[Mapping[str, Any]], TransportResponse]
