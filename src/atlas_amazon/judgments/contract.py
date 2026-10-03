"""The judgment contract.

A judgment is a semantic call that deterministic code can't make: is this
keyword relevant, what intent does it express, does it name an entity, are
two phrases the same concept. Whoever makes it (a fixture today, an LLM in
v0.4b, a human reviewer later), it is recorded as `judgment` Evidence:

    payload = {
      "judgment_type":  "relevance" | "intent" | "entity" | "equivalence",
      "input":          {...},            # exactly what was judged
      "input_hash":     "sha256:<hex>",   # over canonical {"type", "input"}
      "result":         {...},            # schema depends on judgment_type
      "confidence":     0.0-1.0 | null,
      "model":          "<model/provider identifier>",
      "prompt_version": "<prompt or rule version>",
      "rationale":      "<auditable explanation>",
    }

plus the Evidence envelope (provider, marketplace, `retrieved_at` as the
judgment timestamp, run_id, subject).

`parse_judgment` re-validates everything, including recomputing the input
hash, so a judgment can't be silently re-pointed at different input.

Result schemas:

| type        | result                                              |
|-------------|-----------------------------------------------------|
| relevance   | {"score": [0, 1]}                                   |
| intent      | {"label": INTENT_LABELS, "score": [0, 1]} (score = purchase-intent strength) |
| entity      | {"label": ENTITY_LABELS, "entity": str or null}     |
| equivalence | {"equivalent": bool}                                |
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

from atlas_amazon.evidence.identity import make_evidence
from atlas_amazon.jsonvalue import canonical_json, freeze, thaw
from atlas_amazon.keywords.normalize import normalize_text
from atlas_amazon.models import Evidence, EvidenceKind


class JudgmentType(StrEnum):
    RELEVANCE = "relevance"
    INTENT = "intent"
    ENTITY = "entity"
    EQUIVALENCE = "equivalence"


INTENT_LABELS = ("transactional", "commercial_investigation", "informational", "navigational")
ENTITY_LABELS = ("none", "brand", "author", "trademark", "product_line", "other")
# Entities that must not appear in backend keywords (other brands, other authors, marks).
BLOCKING_ENTITY_LABELS = frozenset({"brand", "author", "trademark"})

# Judgments recorded by a person reviewing the run. Same evidence model as any
# other judgment; `model` is "human:<reviewer>". They override model judgments.
HUMAN_PROVIDER = "human"
HUMAN_PROMPT_VERSION = "human-review-v1"

_PAYLOAD_KEYS = frozenset(
    {
        "judgment_type",
        "input",
        "input_hash",
        "result",
        "confidence",
        "model",
        "prompt_version",
        "rationale",
    }
)
EQUIVALENCE_SEPARATOR = " || "


class JudgmentError(ValueError):
    pass


def _unit(value: Any) -> bool:
    return (
        isinstance(value, int | float)
        and not isinstance(value, bool)
        and math.isfinite(value)
        and 0 <= value <= 1
    )


def _check_input(kind: JudgmentType, data: Mapping[str, Any]) -> None:
    if kind is JudgmentType.EQUIVALENCE:
        phrases = data.get("phrases")
        if (
            set(data) != {"phrases"}
            or not isinstance(phrases, tuple | list)
            or len(phrases) != 2
            or not all(isinstance(p, str) and p for p in phrases)
            or list(phrases) != sorted(phrases)
            or phrases[0] == phrases[1]
        ):
            raise JudgmentError("equivalence input must be {'phrases': [a, b]}, sorted, distinct")
        return
    keyword = data.get("keyword")
    if set(data) != {"keyword", "context"} or not isinstance(keyword, str) or not keyword:
        raise JudgmentError(f"{kind} input must be {{'keyword': str, 'context': {{...}}}}")
    if not isinstance(data["context"], Mapping):
        raise JudgmentError("context must be an object")


def _check_result(kind: JudgmentType, result: Mapping[str, Any]) -> None:
    if not isinstance(result, Mapping):
        raise JudgmentError("result must be an object")
    keys = set(result)
    if kind is JudgmentType.RELEVANCE:
        ok = keys == {"score"} and _unit(result["score"])
    elif kind is JudgmentType.INTENT:
        ok = (
            keys == {"label", "score"}
            and result["label"] in INTENT_LABELS
            and _unit(result["score"])
        )
    elif kind is JudgmentType.ENTITY:
        ok = (
            keys == {"label", "entity"}
            and result["label"] in ENTITY_LABELS
            and (result["entity"] is None or isinstance(result["entity"], str))
        )
    else:
        ok = keys == {"equivalent"} and isinstance(result["equivalent"], bool)
    if not ok:
        raise JudgmentError(f"invalid {kind} result: {thaw(result)!r}")


@dataclass(frozen=True, slots=True)
class JudgmentRequest:
    type: JudgmentType
    input: Mapping[str, Any]

    def __post_init__(self) -> None:
        kind = JudgmentType(self.type)
        frozen = freeze(self.input, "input")
        _check_input(kind, frozen)
        object.__setattr__(self, "type", kind)
        object.__setattr__(self, "input", frozen)

    @property
    def input_hash(self) -> str:
        body = canonical_json({"type": self.type.value, "input": self.input})
        return "sha256:" + hashlib.sha256(body.encode("utf-8")).hexdigest()

    @property
    def subject(self) -> str:
        if self.type is JudgmentType.EQUIVALENCE:
            return EQUIVALENCE_SEPARATOR.join(self.input["phrases"])
        return self.input["keyword"]

    @classmethod
    def about_keyword(
        cls, kind: JudgmentType, keyword: str, *, product_title: str, seeds: Sequence[str] = ()
    ) -> JudgmentRequest:
        if kind is JudgmentType.EQUIVALENCE:
            raise JudgmentError("use JudgmentRequest.equivalence for phrase pairs")
        return cls(
            kind,
            {
                "keyword": normalize_text(keyword),
                "context": {"product_title": product_title, "seeds": list(seeds)},
            },
        )

    @classmethod
    def equivalence(cls, a: str, b: str) -> JudgmentRequest:
        return cls(
            JudgmentType.EQUIVALENCE, {"phrases": sorted((normalize_text(a), normalize_text(b)))}
        )


@dataclass(frozen=True, slots=True)
class Judgment:
    """A validated, typed view of one judgment Evidence record."""

    evidence_id: str
    type: JudgmentType
    input: Mapping[str, Any]
    input_hash: str
    result: Mapping[str, Any]
    confidence: float | None
    model: str
    prompt_version: str
    rationale: str
    provider: str
    judged_at: datetime
    # Optional live-call metadata (request hash, response id, served model,
    # usage, and the ID of the semantic_call evidence holding the full exchange).
    call: Mapping[str, Any] | None = None

    @property
    def is_human(self) -> bool:
        return self.provider == HUMAN_PROVIDER

    @property
    def subject(self) -> str:
        return JudgmentRequest(self.type, self.input).subject

    @property
    def score(self) -> float | None:
        return self.result.get("score")

    @property
    def label(self) -> str | None:
        return self.result.get("label")


def judgment_evidence(
    *,
    provider: str,
    request: JudgmentRequest,
    result: Mapping[str, Any],
    confidence: float | None,
    model: str,
    prompt_version: str,
    rationale: str,
    marketplace: str,
    judged_at: datetime,
    run_id: str | None = None,
    source_url: str | None = None,
    call: Mapping[str, Any] | None = None,
) -> Evidence:
    """Build judgment Evidence. Invalid results are rejected at creation time.

    `call` attaches live-call metadata. It is the only optional payload key.
    """
    _check_result(request.type, freeze(result, "result"))
    if confidence is not None and not _unit(confidence):
        raise JudgmentError("confidence must be in [0, 1] or None")
    for name, value in (
        ("model", model),
        ("prompt_version", prompt_version),
        ("rationale", rationale),
    ):
        if not isinstance(value, str) or not value.strip():
            raise JudgmentError(f"{name} must be a non-empty string")
    payload = {
        "judgment_type": request.type.value,
        "input": request.input,
        "input_hash": request.input_hash,
        "result": result,
        "confidence": confidence,
        "model": model,
        "prompt_version": prompt_version,
        "rationale": rationale,
    }
    if call is not None:
        if not isinstance(call, Mapping):
            raise JudgmentError("call metadata must be an object")
        payload["call"] = call
    return make_evidence(
        provider=provider,
        kind=EvidenceKind.JUDGMENT,
        marketplace=marketplace,
        retrieved_at=judged_at,
        payload=payload,
        subject=request.subject,
        run_id=run_id,
        source_url=source_url,
    )


def parse_judgment(evidence: Evidence) -> Judgment:
    if evidence.kind != EvidenceKind.JUDGMENT:
        raise JudgmentError(f"expected judgment evidence, got {evidence.kind!r}")
    p = evidence.payload
    if set(p) - {"call"} != _PAYLOAD_KEYS:
        raise JudgmentError(f"judgment payload keys mismatch: {sorted(p)}")
    if "call" in p and not isinstance(p["call"], Mapping):
        raise JudgmentError("call metadata must be an object")
    try:
        kind = JudgmentType(p["judgment_type"])
    except ValueError:
        raise JudgmentError(f"unknown judgment_type {p['judgment_type']!r}") from None
    request = JudgmentRequest(kind, p["input"])
    if p["input_hash"] != request.input_hash:
        raise JudgmentError("input_hash does not match input")
    if evidence.subject != request.subject:
        raise JudgmentError("evidence subject does not match judged input")
    _check_result(kind, p["result"])
    if p["confidence"] is not None and not _unit(p["confidence"]):
        raise JudgmentError("confidence must be in [0, 1] or null")
    for name in ("model", "prompt_version", "rationale"):
        if not isinstance(p[name], str) or not p[name].strip():
            raise JudgmentError(f"{name} must be a non-empty string")
    return Judgment(
        evidence_id=evidence.id,
        type=kind,
        input=request.input,
        input_hash=p["input_hash"],
        result=p["result"],
        confidence=p["confidence"],
        model=p["model"],
        prompt_version=p["prompt_version"],
        rationale=p["rationale"],
        provider=evidence.provider,
        judged_at=evidence.retrieved_at,
        call=p.get("call"),
    )
