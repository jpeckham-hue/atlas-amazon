"""When a fast-tier answer is re-asked of the strong tier.

Escalation is selective. An item goes to the strong model only for one of
these reasons, recorded on the final judgment (`call.escalation`):

* `failed`: the fast model gave no usable answer for the item (malformed,
  missing, duplicated or mistyped result, or a refused or unparseable batch).
  Transport errors and replay misses are not escalated; they stay unanswered.
* `low_confidence`: the model's own confidence is below `min_confidence`.
* `ambiguous_equivalence`: an equivalence answer below
  `equivalence_min_confidence`. Family grouping would ignore such an answer
  anyway, so a second opinion is the only way it can count.
* `heuristic_disagreement`: a relevance score differs from the deterministic
  term-overlap heuristic by at least `disagreement_threshold` **and** the
  model is not confident (confidence < `disagreement_max_confidence`). The
  heuristic is crude, so a confident model is trusted over it.

`max_escalations` caps escalated items per planned stage, which bounds the
worst case. Items over the cap keep their fast answer (or stay unanswered,
for failures) and the skipped escalation is recorded.

The strong model sees exactly the same batch prompt and never the fast
model's answer, so it is an independent second opinion. Its valid answer
replaces the fast one; if it fails too, a valid fast answer is kept. The
fast exchange stays in the evidence as a `semantic_call` record.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from atlas_amazon.judgments.contract import JudgmentRequest, JudgmentType
from atlas_amazon.keywords.signals import heuristic_relevance, reference_terms_for
from atlas_amazon.semantic import batch


class EscalationReason(StrEnum):
    FAILED = "failed"
    LOW_CONFIDENCE = "low_confidence"
    AMBIGUOUS_EQUIVALENCE = "ambiguous_equivalence"
    HEURISTIC_DISAGREEMENT = "heuristic_disagreement"


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


@dataclass(frozen=True, slots=True)
class EscalationPolicy:
    enabled: bool = True
    on_failure: bool = True
    min_confidence: float = 0.5
    equivalence_min_confidence: float = 0.7  # matches ResearchConfig.min_equivalence_confidence
    disagreement_threshold: float = 0.7
    disagreement_max_confidence: float = 0.8
    max_escalations: int | None = 12
    # Planning assumption only: share of live items expected to escalate.
    expected_rate: float = 0.10

    def __post_init__(self) -> None:
        for name in (
            "min_confidence",
            "equivalence_min_confidence",
            "disagreement_threshold",
            "disagreement_max_confidence",
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
        if not isinstance(confidence, int | float) or isinstance(confidence, bool):
            return None  # validation rejects it; treated as a failure upstream
        if request.type is JudgmentType.EQUIVALENCE:
            if confidence < self.equivalence_min_confidence:
                return (
                    EscalationReason.AMBIGUOUS_EQUIVALENCE,
                    f"confidence {confidence:g} < {self.equivalence_min_confidence:g}",
                )
            return None
        if confidence < self.min_confidence:
            return (
                EscalationReason.LOW_CONFIDENCE,
                f"confidence {confidence:g} < {self.min_confidence:g}",
            )
        if request.type is JudgmentType.RELEVANCE and confidence < self.disagreement_max_confidence:
            context = request.input["context"]
            reference = reference_terms_for(
                str(context.get("product_title", "")), list(context.get("seeds", ()))
            )
            heuristic, _ = heuristic_relevance(request.input["keyword"], reference)
            score = structured.get("score")
            if isinstance(score, int | float) and abs(score - heuristic) >= (
                self.disagreement_threshold
            ):
                return (
                    EscalationReason.HEURISTIC_DISAGREEMENT,
                    f"score {score:g} vs term-overlap heuristic {heuristic:.2f}, "
                    f"confidence {confidence:g}",
                )
        return None
