"""Evaluate candidate judgments (live or replayed model) against reference judgments.

Agreement is reported **per judgment type**, never as one blended score:

| type        | agreement                                  | also reported            |
|-------------|--------------------------------------------|--------------------------|
| relevance   | share with abs(score difference) <= tolerance | mean absolute error   |
| intent      | share with the same label                  | score mean absolute error |
| entity      | share with the same label                  | blocking agreement (*) |
| equivalence | share with the same equivalent value       | -                        |

(*) both or neither label in brand/author/trademark.

Pairs are matched on (type, subject). References with no candidate answer,
and candidate answers with no reference, are counted separately and never
folded into agreement. Every disagreement lists both values and both
rationales.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from atlas_amazon.jsonvalue import thaw
from atlas_amazon.judgments.contract import BLOCKING_ENTITY_LABELS, Judgment, JudgmentType


@dataclass(frozen=True, slots=True)
class Disagreement:
    subject: str
    reference: Any
    candidate: Any
    reference_rationale: str
    candidate_rationale: str
    reference_id: str
    candidate_id: str


@dataclass(frozen=True, slots=True)
class TypeEvaluation:
    type: JudgmentType
    compared: int
    agreed: int
    missing_from_candidate: tuple[str, ...]
    candidate_only: tuple[str, ...]
    disagreements: tuple[Disagreement, ...]
    extra: dict[str, float] = field(default_factory=dict)  # MAE, blocking agreement, ...

    @property
    def agreement_rate(self) -> float | None:
        return self.agreed / self.compared if self.compared else None


@dataclass(frozen=True, slots=True)
class EvaluationReport:
    candidate_label: str
    reference_label: str
    relevance_tolerance: float
    by_type: tuple[TypeEvaluation, ...]

    def get(self, kind: JudgmentType) -> TypeEvaluation:
        return next(t for t in self.by_type if t.type is kind)


def _value(j: Judgment) -> Any:
    if j.type is JudgmentType.RELEVANCE:
        return j.result["score"]
    if j.type is JudgmentType.INTENT:
        return {"label": j.result["label"], "score": j.result["score"]}
    if j.type is JudgmentType.ENTITY:
        return {"label": j.result["label"], "entity": j.result["entity"]}
    return j.result["equivalent"]


def evaluate_judgments(
    candidate: Sequence[Judgment],
    reference: Sequence[Judgment],
    *,
    candidate_label: str = "candidate",
    reference_label: str = "reference",
    relevance_tolerance: float = 0.2,
) -> EvaluationReport:
    def index(items: Sequence[Judgment]) -> dict[tuple[str, str], Judgment]:
        out: dict[tuple[str, str], Judgment] = {}
        for j in items:
            if not j.is_human:
                out.setdefault((j.type.value, j.subject), j)
        return out

    cand, ref = index(candidate), index(reference)
    results = []
    for kind in JudgmentType:
        ref_keys = sorted(s for t, s in ref if t == kind.value)
        cand_keys = sorted(s for t, s in cand if t == kind.value)
        compared = agreed = 0
        disagreements = []
        abs_errors: list[float] = []
        blocking_agree = 0
        for subject in ref_keys:
            c = cand.get((kind.value, subject))
            if c is None:
                continue
            r = ref[(kind.value, subject)]
            compared += 1
            if kind is JudgmentType.RELEVANCE:
                err = abs(c.result["score"] - r.result["score"])
                abs_errors.append(err)
                ok = err <= relevance_tolerance
            elif kind is JudgmentType.INTENT:
                abs_errors.append(abs(c.result["score"] - r.result["score"]))
                ok = c.result["label"] == r.result["label"]
            elif kind is JudgmentType.ENTITY:
                ok = c.result["label"] == r.result["label"]
                blocking_agree += (c.result["label"] in BLOCKING_ENTITY_LABELS) == (
                    r.result["label"] in BLOCKING_ENTITY_LABELS
                )
            else:
                ok = c.result["equivalent"] == r.result["equivalent"]
            if ok:
                agreed += 1
            else:
                disagreements.append(
                    Disagreement(
                        subject,
                        thaw(_value(r)),
                        thaw(_value(c)),
                        r.rationale,
                        c.rationale,
                        r.evidence_id,
                        c.evidence_id,
                    )
                )
        extra: dict[str, float] = {}
        if abs_errors:
            extra["mean_absolute_error"] = sum(abs_errors) / len(abs_errors)
        if kind is JudgmentType.ENTITY and compared:
            extra["blocking_agreement_rate"] = blocking_agree / compared
        results.append(
            TypeEvaluation(
                type=kind,
                compared=compared,
                agreed=agreed,
                missing_from_candidate=tuple(s for s in ref_keys if (kind.value, s) not in cand),
                candidate_only=tuple(s for s in cand_keys if (kind.value, s) not in ref),
                disagreements=tuple(disagreements),
                extra=extra,
            )
        )
    return EvaluationReport(candidate_label, reference_label, relevance_tolerance, tuple(results))


def render_evaluation_markdown(report: EvaluationReport) -> str:
    out = [f"# Judgment evaluation: {report.candidate_label} vs {report.reference_label}", ""]
    out.append("Agreement is reported per type; there is no combined score.")
    out.append("")
    out.append("| Type | Compared | Agreed | Agreement | Other metrics | Missing | Extra |")
    out.append("|---|---|---|---|---|---|---|")
    for t in report.by_type:
        rate = "n/a" if t.agreement_rate is None else f"{t.agreement_rate:.0%}"
        metrics = ", ".join(f"{k} {v:.3f}" for k, v in t.extra.items()) or "-"
        out.append(
            f"| {t.type.value} | {t.compared} | {t.agreed} | {rate} | {metrics} | "
            f"{len(t.missing_from_candidate)} | {len(t.candidate_only)} |"
        )
    out.append("")
    out.append(f"Relevance agreement means abs(score difference) <= {report.relevance_tolerance}.")
    for t in report.by_type:
        if not t.disagreements:
            continue
        out.append("")
        out.append(f"## {t.type.value} disagreements")
        out.append("")
        for d in t.disagreements:
            out.append(
                f"- **{d.subject}**: {report.reference_label} `{d.reference}` vs "
                f"{report.candidate_label} `{d.candidate}`"
            )
            out.append(
                f"  - {report.reference_label}: {d.reference_rationale} (`{d.reference_id}`)"
            )
            out.append(
                f"  - {report.candidate_label}: {d.candidate_rationale} (`{d.candidate_id}`)"
            )
    return "\n".join(out) + "\n"
