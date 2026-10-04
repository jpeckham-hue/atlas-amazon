"""Batched, tiered LLM judgments (the v0.5 default).

`BatchedJudgmentProvider` implements the same `JudgmentProvider` contract as
`LLMJudgmentProvider`: at most one judgment Evidence per request, built with
`judgment_evidence` and re-parsed with `parse_judgment`. Downstream code
can't tell how a judgment was made, except through its recorded metadata.

For one `judge()` call (one stage of a run):

1. **Triage, per judgment.** Strong-tier cache hit -> final. Fast-tier cache
   hit -> final, unless the escalation policy flags it, in which case a
   strong call is *certain*. Everything else is live. (Human overrides and
   deterministic answers were already removed by the run, so they never
   reach a batch.)
2. **Plan** (`plan()` returns this without calling anything): live items in
   fast-tier batches of at most `BatchSettings.max_items`, balanced in size,
   each with an output budget computed from its items; certain escalations
   in strong batches; an escalation reserve for the worst case.
3. **Fast batches.** Budget check per call, send, record the whole exchange
   as one `semantic_call` Evidence, then parse results **by item ID** (see
   `batch.py`). Each valid item becomes its own judgment Evidence with its own
   input hash, result, confidence, rationale, served model, prompt version
   and evidence ID. Invalid items fail alone.
4. **Escalation.** Items the policy flags (failed, low confidence, ambiguous
   equivalence, disagreement with the heuristic), up to its cap, go to the
   strong tier in new batches. The strong judgment records why
   (`call.escalation`), including the fast model's answer and call.
5. **Cache** each valid judgment individually under the existing key
   (type, input hash, provider, model, prompt version), plus the batch
   exchange once (`SemanticCache.put_exchange`).

A budget refusal or disabled live calls stop all further calls of the stage;
unanswered requests fall back to the explicit heuristics.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from atlas_amazon.evidence.identity import make_evidence
from atlas_amazon.jsonvalue import canonical_json, thaw
from atlas_amazon.judgments.contract import (
    JudgmentError,
    JudgmentType,
    judgment_evidence,
    parse_judgment,
)
from atlas_amazon.judgments.contract import JudgmentRequest as Request
from atlas_amazon.models import Evidence, EvidenceKind
from atlas_amazon.semantic import batch as b
from atlas_amazon.semantic.batch import BatchItem, batch_items, chunk, render_batch_input
from atlas_amazon.semantic.budgets import (
    BATCH_OVERHEAD,
    batch_output_budget,
    expected_item_output,
    item_output_budget,
)
from atlas_amazon.semantic.cache import CacheKey, SemanticCache
from atlas_amazon.semantic.escalation import EscalationPolicy, EscalationReason
from atlas_amazon.semantic.llm import build_request
from atlas_amazon.semantic.plan import PlannedCall, SemanticCallPlan
from atlas_amazon.semantic.prompts import JUDGMENT_BATCH, load_template
from atlas_amazon.semantic.records import ensure_no_secrets
from atlas_amazon.semantic.tiers import ModelTier, ModelTiers
from atlas_amazon.semantic.transport import (
    LiveCallsDisabled,
    ReplayMiss,
    Transport,
    TransportResponse,
    request_hash,
)
from atlas_amazon.semantic.usage import BudgetExceeded, UsageLedger, UsageRecord, estimate_tokens

FAST, STRONG = ModelTier.FAST, ModelTier.STRONG


@dataclass(frozen=True, slots=True)
class BatchSettings:
    max_items: int = 40  # per call; also bounded by the template's max_tokens cap

    def __post_init__(self) -> None:
        if self.max_items < 1:
            raise ValueError("max_items must be >= 1")


STRONG_ONLY = "strong_only"


@dataclass(frozen=True, slots=True)
class EscalationEvent:
    run_id: str | None
    item_id: str
    type: str
    subject: str
    reason: str
    detail: str
    # strong_answered | strong_failed, ... | halted, ... | cap_reached
    outcome: str


@dataclass
class _ItemResult:
    status: str
    evidence: Evidence | None = None
    structured: Mapping[str, Any] | None = None
    detail: str = ""
    call: Evidence | None = None
    served_model: str | None = None
    exchange_hash: str | None = None


@dataclass
class _Triage:
    items: tuple[BatchItem, ...]
    strong_cached: dict[str, dict[str, Any]] = field(default_factory=dict)
    fast_cached: dict[str, dict[str, Any]] = field(default_factory=dict)
    certain: dict[str, tuple[dict[str, Any], EscalationReason, str]] = field(default_factory=dict)
    over_cap: list[str] = field(default_factory=list)
    live: list[BatchItem] = field(default_factory=list)  # primary tier
    live_strong: list[BatchItem] = field(default_factory=list)  # strong_types, straight to strong


class _Halt(Exception):
    pass


def _stage(items: Sequence[BatchItem]) -> str:
    kinds = {i.request.type for i in items}
    if kinds == {JudgmentType.EQUIVALENCE}:
        return "equivalence_judgments"
    return "keyword_judgments" if JudgmentType.EQUIVALENCE not in kinds else "judgments"


def _types(items: Sequence[BatchItem]) -> dict[str, int]:
    out: dict[str, int] = {}
    for item in items:
        out[item.request.type.value] = out.get(item.request.type.value, 0) + 1
    return dict(sorted(out.items()))


class BatchedJudgmentProvider:
    """`JudgmentProvider` that batches requests and escalates selectively."""

    def __init__(
        self,
        transport: Transport,
        *,
        tiers: ModelTiers | None = None,
        batching: BatchSettings | None = None,
        escalation: EscalationPolicy | None = None,
        ledger: UsageLedger | None = None,
        cache: SemanticCache | None = None,
        name: str = "anthropic",
        evaluation: str | None = None,
        strong_types: Collection[JudgmentType | str] = (),
    ) -> None:
        """`evaluation="strong_only"` is a benchmarking mode, never a production path:
        every item goes to the strong tier, nothing escalates, and the provider
        refuses to serve a `ResearchRun` (`evaluation_only`). Use it through
        `semantic.comparison.run_strong_comparison`, which keeps its answers
        apart from the production judgments.
        """
        if evaluation not in (None, STRONG_ONLY):
            raise ValueError(f"unknown evaluation mode {evaluation!r}")
        # Judgment types answered by the strong tier from the start (for example
        # relevance only); every other type stays on the fast tier with escalation.
        self.strong_types = frozenset(JudgmentType(t) for t in strong_types)
        self.name = name
        self.transport = transport
        self.tiers = tiers or ModelTiers()
        self.batching = batching or BatchSettings()
        self.evaluation_only = evaluation == STRONG_ONLY
        self.primary = STRONG if self.evaluation_only else FAST
        if self.evaluation_only:
            escalation = EscalationPolicy.disabled()
        self.escalation = escalation if escalation is not None else EscalationPolicy()
        self.usage = ledger or UsageLedger()
        self.cache = cache
        self.template = load_template(JUDGMENT_BATCH)
        self.plans: list[tuple[str | None, SemanticCallPlan]] = []
        self.failures: list[tuple[str, str]] = []  # (purpose:item_id, outcome)
        self.escalation_events: list[EscalationEvent] = []

    # -- requests ------------------------------------------------------------

    def _request(self, tier: ModelTier, items: Sequence[BatchItem]) -> dict[str, Any]:
        settings = self.tiers[tier]
        budget = batch_output_budget(
            [i.request.type for i in items], thinking_allowance=settings.thinking_allowance
        )
        return build_request(settings, self.template, render_batch_input(items), max_tokens=budget)

    def _fit(self, group: tuple[BatchItem, ...]) -> list[tuple[BatchItem, ...]]:
        """Split a group until its answer budget fits under the template cap."""
        if len(group) <= 1 or batch_output_budget(i.request.type for i in group) <= (
            self.template.max_tokens
        ):
            return [group]
        mid = len(group) // 2
        return self._fit(group[:mid]) + self._fit(group[mid:])

    def _batches(self, items: Sequence[BatchItem]) -> list[tuple[BatchItem, ...]]:
        out: list[tuple[BatchItem, ...]] = []
        for group in chunk(tuple(items), self.batching.max_items):
            out += self._fit(group)
        return out

    # -- cache ---------------------------------------------------------------

    def _key(self, tier: ModelTier, request: Request) -> CacheKey:
        return CacheKey(
            request.type.value,
            request.input_hash,
            self.name,
            self.tiers[tier].model,
            self.template.version,
        )

    def _cached(self, tier: ModelTier, item: BatchItem) -> dict[str, Any] | None:
        if self.cache is None:
            return None
        found = self.cache.lookup(self._key(tier, item.request), self.template.fingerprint)
        entry = found.entry
        if entry is None or self.cache.exchange(entry["exchange"]) is None:
            return None
        return entry

    # -- planning ------------------------------------------------------------

    def _triage(self, items: tuple[BatchItem, ...]) -> _Triage:
        t = _Triage(items)
        cap = self.escalation.max_escalations if self.escalation.can_escalate else 0
        for item in items:
            strong = None if self.evaluation_only else self._cached(STRONG, item)
            if strong is not None:
                t.strong_cached[item.id] = strong
                continue
            if item.request.type in self.strong_types and not self.evaluation_only:
                t.live_strong.append(item)
                continue
            fast = self._cached(self.primary, item)
            if fast is None:
                t.live.append(item)
                continue
            why = self.escalation.reason(item.request, status=b.OK, structured=fast["structured"])
            if why is not None and (cap is None or len(t.certain) < cap):
                t.certain[item.id] = (fast, *why)
            else:
                if why is not None:
                    t.over_cap.append(item.id)
                t.fast_cached[item.id] = fast
        return t

    def _planned(self, tier: ModelTier, items: Sequence[BatchItem], *, exact: bool) -> PlannedCall:
        settings = self.tiers[tier]
        request = self._request(tier, items)
        input_tokens = estimate_tokens(request)
        expected_out = (
            BATCH_OVERHEAD
            + sum(expected_item_output(i.request.type) for i in items)
            + settings.thinking_allowance // 4
        )
        price = self.usage.pricing.get(settings.model)
        return PlannedCall(
            tier=tier.value,
            model=settings.model,
            items=len(items),
            types=_types(items),
            max_tokens=request["max_tokens"],
            input_tokens=input_tokens,
            expected_output_tokens=expected_out,
            expected_cost_usd=None if price is None else price.cost(input_tokens, expected_out),
            worst_case_cost_usd=None
            if price is None
            else price.cost(input_tokens, request["max_tokens"]),
            request_hash=request_hash(request) if exact else None,
            item_ids=tuple(i.id for i in items) if exact else (),
        )

    def _plan_from(self, t: _Triage) -> SemanticCallPlan:
        by_id = {i.id: i for i in t.items}
        fast_calls = tuple(
            self._planned(self.primary, g, exact=True) for g in self._batches(t.live)
        ) + tuple(self._planned(STRONG, g, exact=True) for g in self._batches(t.live_strong))
        certain_items = [by_id[i] for i in t.certain]
        certain_calls = tuple(
            self._planned(STRONG, g, exact=True) for g in self._batches(certain_items)
        )
        reserve: tuple[PlannedCall, ...] = ()
        expected_calls, expected_cost = 0, 0.0
        notes: list[str] = []
        policy = self.escalation
        if policy.can_escalate and t.live:
            room = (
                len(t.live)
                if policy.max_escalations is None
                else max(0, policy.max_escalations - len(t.certain))
            )
            # Worst case: the items with the largest answer budgets all escalate.
            worst_items = sorted(t.live, key=lambda i: (-item_output_budget(i.request.type), i.id))[
                :room
            ]
            reserve = tuple(
                self._planned(STRONG, g, exact=False)
                for g in self._batches(sorted(worst_items, key=lambda i: (i.request.subject, i.id)))
            )
            expected_items = min(room, policy.expected_rate * len(t.live))
            if expected_items > 0:
                # Fewer than one expected item: most likely no strong call at all
                # (its probability-weighted cost is still counted below).
                if expected_items >= 1:
                    expected_calls = math.ceil(expected_items / self.batching.max_items)
                everything = self._planned(STRONG, t.live, exact=False)
                per_item = (
                    None
                    if everything.expected_cost_usd is None
                    else everything.expected_cost_usd / len(t.live)
                )
                expected_cost = None if per_item is None else per_item * expected_items
            notes.append(
                f"escalation reserve: up to {room} of {len(t.live)} live items "
                f"(expected {expected_items:.1f} at rate {policy.expected_rate:g})"
            )
        if t.over_cap:
            notes.append(
                f"{len(t.over_cap)} cached answers over the escalation cap keep their fast answer"
            )
        return SemanticCallPlan(
            stage=_stage(t.items),
            provider=self.name,
            requested=len(t.items),
            cache_hits=len(t.strong_cached) + len(t.fast_cached) + len(t.certain),
            live=len(t.live) + len(t.live_strong),
            batches=fast_calls,
            escalations=certain_calls,
            escalation_reserve=reserve,
            expected_escalation_calls=expected_calls,
            expected_escalation_cost_usd=expected_cost,
            pricing_as_of=self.usage.pricing.as_of,
            notes=tuple(notes),
        )

    def plan(
        self, requests: Sequence[Request], *, marketplace: str = "", run_id: str | None = None
    ) -> SemanticCallPlan:
        """What `judge(requests)` would call, and cost, right now. Makes no calls."""
        return self._plan_from(self._triage(batch_items(requests)))

    # -- evidence ------------------------------------------------------------

    def _call_evidence(
        self,
        *,
        tier: str,
        item_ids: Sequence[str],
        request: Mapping[str, Any],
        response: TransportResponse,
        marketplace: str,
        run_id: str | None,
    ) -> Evidence:
        rhash = request_hash(request)
        purpose = f"{JUDGMENT_BATCH}:{tier}"
        payload = {
            "purpose": purpose,
            "prompt": {
                "name": self.template.name,
                "version": self.template.version,
                "fingerprint": self.template.fingerprint,
            },
            "tier": tier,
            "items": list(item_ids),
            "input_hash": "sha256:"
            + hashlib.sha256(canonical_json(sorted(item_ids)).encode("utf-8")).hexdigest(),
            "request_hash": rhash,
            "request": thaw(request),
            "response": response.to_dict(),
        }
        ensure_no_secrets(payload, "semantic_call evidence")
        return make_evidence(
            provider=self.name,
            kind=EvidenceKind.SEMANTIC_CALL,
            marketplace=marketplace,
            retrieved_at=datetime.fromisoformat(response.responded_at),
            payload=payload,
            subject=f"{purpose}:{rhash}",
            run_id=run_id,
        )

    def _judgment(
        self,
        *,
        tier: str,
        item_id: str,
        request: Request,
        structured: Mapping[str, Any],
        call: Evidence,
        marketplace: str,
        run_id: str | None,
        escalation: Mapping[str, Any] | None,
    ) -> Evidence:
        response = TransportResponse.from_dict(call.payload["response"])
        data = dict(thaw(structured))
        confidence = data.pop("confidence")
        rationale = data.pop("rationale")
        if request.type is JudgmentType.ENTITY:
            data["entity"] = data.get("entity") or None
        meta: dict[str, Any] = {
            "call_evidence_id": call.id,
            "request_hash": call.payload["request_hash"],
            "response_id": response.id,
            "requested_model": call.payload["request"]["model"],
            "served_model": response.model,
            "stop_reason": response.stop_reason,
            "usage": thaw(response.usage),  # of the whole batch call
            "synthetic": response.synthetic,
            "tier": tier,
            "batch": {"item_id": item_id, "items": len(call.payload["items"])},
        }
        if escalation is not None:
            meta["escalation"] = thaw(escalation)
        evidence = judgment_evidence(
            provider=self.name,
            request=request,
            result=data,
            confidence=confidence,
            model=response.model,
            prompt_version=self.template.version,
            rationale=rationale,
            marketplace=marketplace,
            judged_at=datetime.fromisoformat(response.responded_at),
            run_id=run_id,
            source_url=f"semantic-call://{call.id}",
            call=meta,
        )
        parse_judgment(evidence)  # the same parser the run uses; never bypassed
        return evidence

    def _cached_call(
        self, exchange_hash: str, marketplace: str, run_id: str | None
    ) -> Evidence | None:
        assert self.cache is not None
        value = self.cache.exchange(exchange_hash)
        if value is None:
            return None
        return self._call_evidence(
            tier=value["tier"],
            item_ids=value["items"],
            request=value["request"],
            response=TransportResponse.from_dict(value["response"]),
            marketplace=marketplace,
            run_id=run_id,
        )

    def _from_cache(
        self,
        tier: ModelTier,
        item: BatchItem,
        entry: Mapping[str, Any],
        marketplace: str,
        run_id: str | None,
        calls: dict[str, Evidence],
    ) -> _ItemResult:
        call = self._cached_call(entry["exchange"], marketplace, run_id)
        assert call is not None  # _cached checked the exchange exists
        calls.setdefault(call.id, call)
        escalation = entry.get("escalation")
        if escalation and escalation.get("from_request_hash"):
            origin = self._cached_call(escalation["from_request_hash"], marketplace, run_id)
            if origin is not None:
                calls.setdefault(origin.id, origin)
        evidence = self._judgment(
            tier=tier.value,
            item_id=item.id,
            request=item.request,
            structured=entry["structured"],
            call=call,
            marketplace=marketplace,
            run_id=run_id,
            escalation=escalation,
        )
        self.usage.record(
            UsageRecord(
                run_id=run_id,
                provider=self.name,
                model=self.tiers[tier].model,
                purpose=f"{JUDGMENT_BATCH}:{tier.value}",
                prompt_version=self.template.version,
                source="cache",
                outcome="ok",
                estimated_cost_usd=0.0,
                tier=tier.value,
            )
        )
        return _ItemResult(
            b.OK,
            evidence,
            entry["structured"],
            call=call,
            served_model=call.payload["response"]["model"],
            exchange_hash=entry["exchange"],
        )

    # -- execution -----------------------------------------------------------

    def _record_call(
        self,
        *,
        run_id: str | None,
        tier: ModelTier,
        model: str,
        source: str,
        outcome: str,
        items: int,
        judgments: int = 0,
        escalated: int = 0,
        usage: Mapping[str, Any] | None = None,
        detail: str = "",
        item_failures: Mapping[str, int] | None = None,
    ) -> None:
        usage = usage or {}
        cost = self.usage.cost_of(model, usage) if source == "live" else None
        self.usage.record(
            UsageRecord(
                run_id=run_id,
                provider=self.name,
                model=model,
                purpose=f"{JUDGMENT_BATCH}:{tier.value}",
                prompt_version=self.template.version,
                source=source,
                outcome=outcome,
                input_tokens=usage.get("input_tokens"),
                output_tokens=usage.get("output_tokens"),
                cache_read_tokens=usage.get("cache_read_input_tokens"),
                cache_write_tokens=usage.get("cache_creation_input_tokens"),
                estimated_cost_usd=cost,
                detail=detail,
                tier=tier.value,
                items=items,
                judgments=judgments,
                escalated=escalated,
                item_failures=tuple(sorted((item_failures or {}).items())),
            )
        )

    def _run_batch(
        self,
        tier: ModelTier,
        group: tuple[BatchItem, ...],
        *,
        marketplace: str,
        run_id: str | None,
        escalations: Mapping[str, Mapping[str, Any]] | None = None,
        calls: dict[str, Evidence],
    ) -> dict[str, _ItemResult]:
        """One call. Returns a result per item. Raises _Halt to stop the stage."""
        settings = self.tiers[tier]
        request = self._request(tier, group)
        escalated = len(escalations or {})
        purpose = f"{JUDGMENT_BATCH}:{tier.value}"
        if self.transport.is_live:
            try:
                self.usage.authorize(run_id=run_id, model=settings.model, request=request)
            except BudgetExceeded as exc:
                self._record_call(
                    run_id=run_id,
                    tier=tier,
                    model=settings.model,
                    source="skipped",
                    outcome="budget",
                    items=len(group),
                    escalated=escalated,
                    detail=exc.reason,
                )
                raise _Halt from exc
        source = "live" if self.transport.is_live else "replay"
        try:
            response = self.transport.send(request)
        except LiveCallsDisabled as exc:
            raise _Halt from exc
        except Exception as exc:  # replay misses, API and network errors: contained
            outcome = "replay_miss" if isinstance(exc, ReplayMiss) else "error"
            self._record_call(
                run_id=run_id,
                tier=tier,
                model=settings.model,
                source=source,
                outcome=outcome,
                items=len(group),
                escalated=escalated,
                detail=str(exc) if outcome == "replay_miss" else type(exc).__name__,
            )
            for item in group:
                self.failures.append((f"{purpose}:{item.id}", outcome))
            return {item.id: _ItemResult(outcome) for item in group}

        call = self._call_evidence(
            tier=tier.value,
            item_ids=[i.id for i in group],
            request=request,
            response=response,
            marketplace=marketplace,
            run_id=run_id,
        )
        calls.setdefault(call.id, call)
        parsed = b.parse_batch_response(group, response.text, response.stop_reason)
        results: dict[str, _ItemResult] = {}
        for item in group:
            outcome = parsed.outcomes[item.id]
            result = _ItemResult(
                outcome.status,
                structured=outcome.structured,
                detail=outcome.detail,
                call=call,
                served_model=response.model,
                exchange_hash=call.payload["request_hash"],
            )
            if outcome.ok:
                try:
                    result.evidence = self._judgment(
                        tier=tier.value,
                        item_id=item.id,
                        request=item.request,
                        structured=outcome.structured,  # type: ignore[arg-type]
                        call=call,
                        marketplace=marketplace,
                        run_id=run_id,
                        escalation=(escalations or {}).get(item.id),
                    )
                except (JudgmentError, KeyError, TypeError, ValueError) as exc:
                    result.status = b.MALFORMED
                    result.detail = f"{type(exc).__name__}: {exc}"
            if result.status != b.OK:
                self.failures.append((f"{purpose}:{item.id}", result.status))
            results[item.id] = result

        ok = [i for i in group if results[i.id].status == b.OK]
        failed: dict[str, int] = {}
        for r in results.values():
            if r.status != b.OK:
                failed[r.status] = failed.get(r.status, 0) + 1
        if parsed.batch_error is not None:
            outcome = "refusal" if parsed.batch_error == b.REFUSAL else "malformed"
        else:
            outcome = "ok" if not failed else ("partial" if ok else "malformed")
        notes = list(parsed.notes)
        if parsed.out_of_order:
            notes.append("results out of request order (matched by id)")
        if failed:
            notes.append("item failures: " + ", ".join(f"{k} {n}" for k, n in failed.items()))
        self._record_call(
            run_id=run_id,
            tier=tier,
            model=response.model,
            source=source,
            outcome=outcome,
            items=len(group),
            judgments=len(ok),
            escalated=escalated,
            usage=response.usage,
            detail="; ".join(notes),
            item_failures=failed,
        )
        if ok and self.cache is not None:
            self.cache.put_exchange(
                call.payload["request_hash"],
                {
                    "tier": tier.value,
                    "items": [i.id for i in group],
                    "request": thaw(request),
                    "response": response.to_dict(),
                },
            )
            for item in ok:
                self.cache.put(
                    self._key(tier, item.request),
                    self.template.fingerprint,
                    {
                        "item_id": item.id,
                        "structured": thaw(results[item.id].structured),
                        "exchange": call.payload["request_hash"],
                        "escalation": thaw((escalations or {}).get(item.id)),
                    },
                )
        return results

    def judge(
        self, requests: Sequence[Request], *, marketplace: str, run_id: str | None = None
    ) -> list[Evidence]:
        items = batch_items(requests)
        if not items:
            return []
        triage = self._triage(items)
        plan = self._plan_from(triage)
        self.plans.append((run_id, plan))
        by_id = {i.id: i for i in items}
        calls: dict[str, Evidence] = {}
        final: dict[str, _ItemResult] = {}
        fast: dict[str, _ItemResult] = {}

        for iid, entry in triage.strong_cached.items():
            final[iid] = self._from_cache(STRONG, by_id[iid], entry, marketplace, run_id, calls)
        for iid, entry in triage.fast_cached.items():
            final[iid] = self._from_cache(
                self.primary, by_id[iid], entry, marketplace, run_id, calls
            )
        for iid, (entry, _, _) in triage.certain.items():
            fast[iid] = self._from_cache(
                self.primary, by_id[iid], entry, marketplace, run_id, calls
            )

        halted = False
        try:
            for group in self._batches(triage.live):
                fast.update(
                    self._run_batch(
                        self.primary, group, marketplace=marketplace, run_id=run_id, calls=calls
                    )
                )
            for group in self._batches(triage.live_strong):
                for iid, result in self._run_batch(
                    STRONG, group, marketplace=marketplace, run_id=run_id, calls=calls
                ).items():
                    if result.status == b.OK:
                        final[iid] = result
        except _Halt:
            halted = True

        # Escalation: certain ones first, then failures, then the rest, by id.
        flagged: list[tuple[str, EscalationReason, str]] = [
            (iid, reason, detail) for iid, (_, reason, detail) in triage.certain.items()
        ]
        fresh = []
        for item in triage.live:
            result = fast.get(item.id)
            if result is None:
                continue
            why = self.escalation.reason(
                item.request, status=result.status, structured=result.structured
            )
            if why is not None:
                fresh.append((item.id, *why))
        fresh.sort(key=lambda x: (x[1] is not EscalationReason.FAILED, x[0]))
        flagged += fresh
        cap = self.escalation.max_escalations
        chosen = flagged if cap is None else flagged[: max(0, cap)]
        for iid, reason, detail in flagged[len(chosen) :]:
            self._event(run_id, by_id[iid], reason, detail, "cap_reached")
        meta: dict[str, dict[str, Any]] = {}
        for iid, reason, detail in chosen:
            origin = fast[iid]
            meta[iid] = {
                "reason": reason.value,
                "detail": detail,
                "from_model": origin.served_model,
                "from_status": origin.status,
                "from_call_evidence_id": origin.call.id if origin.call is not None else None,
                "from_request_hash": origin.exchange_hash,
                "from_result": None
                if origin.evidence is None
                else thaw(parse_judgment(origin.evidence).result),
                "from_confidence": None
                if origin.evidence is None
                else parse_judgment(origin.evidence).confidence,
            }
        strong: dict[str, _ItemResult] = {}
        if chosen and not halted:
            try:
                for group in self._batches([by_id[iid] for iid, _, _ in chosen]):
                    strong.update(
                        self._run_batch(
                            STRONG,
                            group,
                            marketplace=marketplace,
                            run_id=run_id,
                            escalations={i.id: meta[i.id] for i in group},
                            calls=calls,
                        )
                    )
            except _Halt:
                halted = True

        for iid, reason, detail in chosen:
            s, f = strong.get(iid), fast[iid]
            if s is not None and s.status == b.OK:
                final[iid], outcome = s, "strong_answered"
            else:
                if f.status == b.OK:
                    final[iid] = f
                outcome = "halted" if s is None else "strong_failed"
                outcome += ", kept fast answer" if f.status == b.OK else ", unanswered"
            self._event(run_id, by_id[iid], reason, detail, outcome)
        for iid, result in fast.items():
            if iid not in final and iid not in meta and result.status == b.OK:
                final[iid] = result

        out: list[Evidence] = list(calls.values())
        out += [final[i.id].evidence for i in items if i.id in final]  # type: ignore[misc]
        return out

    def _event(
        self, run_id: str | None, item: BatchItem, reason: EscalationReason, detail: str, outcome
    ) -> None:
        self.escalation_events.append(
            EscalationEvent(
                run_id,
                item.id,
                item.request.type.value,
                item.request.subject,
                reason.value,
                detail,
                outcome,
            )
        )

    def plans_for(self, run_id: str | None) -> tuple[SemanticCallPlan, ...]:
        return tuple(p for rid, p in self.plans if rid == run_id)
