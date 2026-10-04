"""When a fast-tier answer is re-asked of the strong tier (v0.7: risk signals).

The v0.6 live baseline showed that the fast model's self-reported confidence
is not a useful trigger: it ranged 0.60-0.99, and every disagreement with the
fixture judgments came at high confidence. Confidence is kept as metadata,
but escalation is now driven by **deterministic risk signals**, each checked
against first-party input or plain-code rules. Every escalated judgment
records the exact reason in `call.escalation`.

* `failed`: no usable fast answer (missing, duplicate, mistyped or
  malformed item; refused or unparseable batch).
* `feature_underrated`: the keyword appears verbatim in a first-party
  feature, subtitle or description, yet relevance < `feature_min_relevance`.
* `lexical_disagreement`: relevance differs by >= `lexical_threshold` from
  the feature-aware lexical baseline (the share of the keyword's words found
  in the product's first-party text).
* `intent_structure`: `transactional` for a generic head term (<= 2 words,
  all from the title, seeds or category) or for a bare attribute ("leak
  proof", "bpa free").
* `entity_conflict`: a blocking label (brand, author, trademark) whose entity
  is the seller's own title, subtitle, brand or author.
* `equivalence_conflict`: the answer contradicts the head-noun rule (same
  head noun: same product; different head noun: different product, as in
  "bottle water" vs "water bottle").
* `low_confidence_with_risk`: confidence < `low_confidence` **and** a weaker
  lexical gap (>= `weak_lexical_gap`). Low confidence alone never escalates.

Recipe entities (for example KDP program names) never reach the model: the
deterministic rules answer them first, so they cannot conflict.

Transport errors and replay misses are not escalated. At most
`max_escalations` items per stage escalate (failures first). The strong
model gets the same batch prompt and never sees the fast answer; its valid
answer replaces the fast one, and if it fails a valid fast answer is kept.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from atlas_amazon.judgments.context import first_party_text
from atlas_amazon.judgments.contract import BLOCKING_ENTITY_LABELS, JudgmentRequest, JudgmentType
from atlas_amazon.keywords.candidates import EDGE_STOPWORDS
from atlas_amazon.keywords.coverage import contains_phrase
from atlas_amazon.keywords.families import UNIT_WORDS, _block_reason
from atlas_amazon.keywords.normalize import fold_plural, keyword_key, tokenize
from atlas_amazon.keywords.signals import heuristic_relevance
from atlas_amazon.semantic import batch

CONNECTORS = frozenset({"for", "with", "of", "in", "to", "on"})


class EscalationReason(StrEnum):
    FAILED = "failed"
    FEATURE_UNDERRATED = "feature_underrated"
    LEXICAL_DISAGREEMENT = "lexical_disagreement"
    INTENT_STRUCTURE = "intent_structure"
    ENTITY_CONFLICT = "entity_conflict"
    EQUIVALENCE_CONFLICT = "equivalence_conflict"
    LOW_CONFIDENCE_WITH_RISK = "low_confidence_with_risk"


# Item outcomes that mean the model answered badly (worth a second opinion).
ESCALATABLE_FAILURES = frozenset(
    {
        batch.MISSING,
        batch.DUPLICATE,
        batch.TYPE_MISMATCH,
        batch.MALFORMED,
        batch.REFUSAL,
        batch.BATCH_MALFORMED,
    }
)


def _unit(value: float, name: str) -> None:
    if not 0 <= value <= 1:
        raise ValueError(f"{name} must be within [0, 1]")


def _content(phrase: str) -> list[str]:
    return [fold_plural(t) for t in tokenize(phrase) if t not in EDGE_STOPWORDS]


def head_noun(phrase: str) -> str | None:
    """The product noun: the last content word before a connector, else the last one."""
    tokens = tokenize(phrase)
    for i, token in enumerate(tokens):
        if token in CONNECTORS and i > 0:
            tokens = tokens[:i]
            break
    content = [fold_plural(t) for t in tokens if t not in EDGE_STOPWORDS]
    return content[-1] if content else None


def lexical_relevance(keyword: str, context: Mapping[str, Any]) -> float:
    """Share of the keyword's words found in the product's first-party text."""
    value, _ = heuristic_relevance(keyword, first_party_text(context))
    return value


def stated_feature(keyword: str, context: Mapping[str, Any]) -> str | None:
    """A first-party feature, subtitle or description containing the keyword verbatim."""
    key = keyword_key(keyword)
    if len(key) < 1:
        return None
    sources: Sequence[str] = [
        *[str(f) for f in context.get("features", ())],
        *[str(context[k]) for k in ("subtitle", "description") if context.get(k)],
    ]
    for text in sources:
        if contains_phrase(keyword_key(text), key):
            return text
    return None


def _structure(keyword: str, context: Mapping[str, Any]) -> str | None:
    """'head term' / 'bare attribute' when the keyword's shape implies browsing."""
    tokens = [t for t in tokenize(keyword) if t not in EDGE_STOPWORDS]
    if not tokens or len(tokens) > 2:
        return None
    if _block_reason(tokens) is not None and not any(
        t.isdigit() or t in UNIT_WORDS for t in tokens
    ):
        return "bare attribute"
    known = {
        fold_plural(t)
        for text in (
            str(context.get("product_title", "")),
            str(context.get("category", "")).replace("-", " "),
            *[str(s) for s in context.get("seeds", ())],
        )
        for t in tokenize(text)
    }
    if all(fold_plural(t) in known for t in tokens):
        return "generic head term"
    return None


@dataclass(frozen=True, slots=True)
class EscalationPolicy:
    enabled: bool = True
    on_failure: bool = True
    feature_min_relevance: float = 0.6
    lexical_threshold: float = 0.6
    intent_structure: bool = True
    entity_conflicts: bool = True
    equivalence_conflicts: bool = True
    low_confidence: float = 0.6
    weak_lexical_gap: float = 0.35
    max_escalations: int | None = 12
    # Planning assumption only: share of live items expected to escalate.
    expected_rate: float = 0.15

    def __post_init__(self) -> None:
        for name in (
            "feature_min_relevance",
            "lexical_threshold",
            "low_confidence",
            "weak_lexical_gap",
            "expected_rate",
        ):
            _unit(getattr(self, name), name)
        if self.max_escalations is not None and self.max_escalations < 0:
            raise ValueError("max_escalations must be >= 0")

    @classmethod
    def disabled(cls) -> EscalationPolicy:
        return cls(enabled=False, expected_rate=0.0, max_escalations=0)

    @property
    def can_escalate(self) -> bool:
        return self.enabled and self.max_escalations != 0

    def reason(
        self,
        request: JudgmentRequest,
        *,
        status: str,
        structured: Mapping[str, Any] | None,
    ) -> tuple[EscalationReason, str] | None:
        """Why this fast-tier outcome should escalate, or None."""
        if not self.enabled:
            return None
        if status != batch.OK:
            if self.on_failure and status in ESCALATABLE_FAILURES:
                return EscalationReason.FAILED, f"fast tier: {status}"
            return None
        assert structured is not None
        confidence = structured.get("confidence")
        conf = f"confidence {confidence:g}" if isinstance(confidence, int | float) else ""
        if request.type is JudgmentType.EQUIVALENCE:
            return self._equivalence(request, structured, conf)
        keyword = request.input["keyword"]
        context = request.input["context"]
        if request.type is JudgmentType.RELEVANCE:
            score = structured.get("score")
            if not isinstance(score, int | float):
                return None
            feature = stated_feature(keyword, context)
            if feature is not None and score < self.feature_min_relevance:
                return (
                    EscalationReason.FEATURE_UNDERRATED,
                    f"score {score:g} < {self.feature_min_relevance:g} but first-party text "
                    f"states it: {feature!r} ({conf})",
                )
            baseline = lexical_relevance(keyword, context)
            gap = abs(score - baseline)
            if gap >= self.lexical_threshold:
                return (
                    EscalationReason.LEXICAL_DISAGREEMENT,
                    f"score {score:g} vs feature-aware lexical baseline {baseline:.2f} ({conf})",
                )
            if (
                isinstance(confidence, int | float)
                and confidence < self.low_confidence
                and gap >= self.weak_lexical_gap
            ):
                return (
                    EscalationReason.LOW_CONFIDENCE_WITH_RISK,
                    f"{conf} < {self.low_confidence:g} and lexical gap {gap:.2f}",
                )
        elif request.type is JudgmentType.INTENT and self.intent_structure:
            shape = _structure(keyword, context)
            if shape is not None and structured.get("label") == "transactional":
                return (
                    EscalationReason.INTENT_STRUCTURE,
                    f"'transactional' for a {shape} ({conf})",
                )
        elif request.type is JudgmentType.ENTITY and self.entity_conflicts:
            label, entity = structured.get("label"), structured.get("entity") or ""
            if label in BLOCKING_ENTITY_LABELS and entity:
                own = {
                    fold_plural(t)
                    for key in ("product_title", "subtitle", "brand", "author")
                    for t in tokenize(str(context.get(key, "")))
                    if t not in EDGE_STOPWORDS
                }
                words = _content(str(entity))
                if words and all(w in own for w in words):
                    return (
                        EscalationReason.ENTITY_CONFLICT,
                        f"'{entity}' labeled {label} but it is the seller's own metadata ({conf})",
                    )
        return None

    def _equivalence(
        self, request: JudgmentRequest, structured: Mapping[str, Any], conf: str
    ) -> tuple[EscalationReason, str] | None:
        if not self.equivalence_conflicts:
            return None
        a, b = request.input["phrases"]
        ha, hb = head_noun(a), head_noun(b)
        if ha is None or hb is None:
            return None
        expected = ha == hb
        if bool(structured.get("equivalent")) != expected:
            rule = "same head noun" if expected else f"different head nouns ({ha!r}, {hb!r})"
            return (
                EscalationReason.EQUIVALENCE_CONFLICT,
                f"equivalent={structured.get('equivalent')} contradicts the {rule} ({conf})",
            )
        return None
