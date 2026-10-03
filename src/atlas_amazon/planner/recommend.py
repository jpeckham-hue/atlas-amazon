"""Deterministic recommendations from ranked keywords. No copywriting.

* **Backend plan.** Packs ranked keywords, best first, into the recipe's
  backend field using the v0.1 packers. Keywords hitting an enabled
  `prohibited_terms` rule on the backend field are excluded first, with the
  rule ID recorded. The result is a concrete `Proposal` citing the
  evidence of every keyword that contributed. No proposal is made when
  nothing packs, or when the current value already equals the packing.
* **Keyword gaps.** Top-N ranked keywords whose exact phrase appears in no
  weighted listing field.
* **Placement upgrades.** Top-N ranked keywords present only in a
  lower-weight field than the best available one.

Gaps and upgrades are `Recommendation`s, not Proposals: they say *what* is
missing and *where* it would count more, but write no copy. Every one
carries the evidence IDs of the keyword's score.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas_amazon.audit.listing import find_terms
from atlas_amazon.backend.packing import Exclusion, pack_backend_bytes, pack_keyword_slots
from atlas_amazon.keywords.coverage import CoverageReport, compute_coverage
from atlas_amazon.keywords.normalize import normalize_text, tokenize
from atlas_amazon.keywords.scoring import KeywordScore
from atlas_amazon.models import Listing
from atlas_amazon.planner.proposal import Proposal
from atlas_amazon.recipes.schema import Recipe


@dataclass(frozen=True, slots=True)
class RuleExclusion:
    keyword: str
    rule_id: str
    terms: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BackendPlan:
    field_name: str
    mode: str
    proposal: Proposal | None
    packed_keywords: tuple[str, ...]  # ranked keywords that contributed packed content
    exclusions: tuple[Exclusion, ...]  # from the packer
    rule_exclusions: tuple[RuleExclusion, ...]  # removed before packing
    retained: tuple[str, ...]  # current backend content kept after ranked keywords (unscored)
    used: int  # bytes (bytes mode) or filled slots (slots mode)
    capacity: int
    note: str


class RecommendationKind(StrEnum):
    KEYWORD_GAP = "keyword_gap"
    PLACEMENT_UPGRADE = "placement_upgrade"


@dataclass(frozen=True, slots=True)
class Recommendation:
    kind: RecommendationKind
    keyword: str
    rank: int  # 1-based position in the ranking
    score: float
    current_fields: tuple[str, ...]  # weighted fields that contain the exact phrase
    suggested_fields: tuple[str, ...]  # higher-weight fields, best first
    blocked_fields: tuple[tuple[str, str], ...]  # (field, rule_id) where recipe rules forbid it
    reason: str
    evidence_ids: tuple[str, ...]
    heuristic_signals: tuple[str, ...]
    covered_by_proposal: str | None  # backend proposal that already packs it, if any


def _prohibiting_rule(recipe: Recipe, field_name: str, text: str) -> RuleExclusion | None:
    """The first enabled prohibited_terms rule on `field_name` that `text` violates."""
    for rule in recipe.enabled_rules():
        if rule.check == "prohibited_terms" and field_name in rule.fields:
            hits = find_terms(text, rule.params["terms"])
            if hits:
                return RuleExclusion(text, rule.id, tuple(hits))
    return None


def _evidence_for(ranked: Sequence[KeywordScore], keywords: set[str]) -> tuple[str, ...]:
    ids: dict[str, None] = {}
    for score in ranked:
        if score.keyword in keywords:
            ids.update(dict.fromkeys(score.evidence_ids))
    return tuple(ids)


def plan_backend(
    recipe: Recipe, listing: Listing, ranked: Sequence[KeywordScore], *, created_at: datetime
) -> BackendPlan | None:
    backend = recipe.backend
    if backend is None:
        return None
    spec = recipe.fields[backend.field_name]
    rule_excluded: list[RuleExclusion] = []
    eligible: list[KeywordScore] = []
    for score in ranked:
        hit = _prohibiting_rule(recipe, backend.field_name, score.keyword)
        if hit:
            rule_excluded.append(hit)
        else:
            eligible.append(score)
    visible = [listing.text(name) for name in backend.visible_fields]
    # Current backend content is kept at the lowest priority instead of being
    # silently dropped. It is unscored, and the rationale says so.
    # In bytes mode the field is a bag of words; in slots mode each box is a phrase.
    ranked_keys = {s.keyword for s in ranked}
    segments = listing.segments(backend.field_name)
    if backend.mode == "bytes":
        pieces = [token for seg in segments for token in tokenize(seg)]
    else:
        pieces = [normalize_text(seg) for seg in segments]
    current_items = [p for p in pieces if p and p not in ranked_keys]
    retained_candidates = []
    for item in dict.fromkeys(current_items):
        hit = _prohibiting_rule(recipe, backend.field_name, item)
        if hit:
            rule_excluded.append(hit)
        else:
            retained_candidates.append(item)
    ordered = [s.keyword for s in eligible] + retained_candidates

    if backend.mode == "bytes":
        assert spec.max_bytes is not None  # guaranteed by the loader
        packed = pack_backend_bytes(
            ordered,
            spec.max_bytes,
            visible=visible,
            stopwords=backend.stopwords,
            count_spaces=backend.count_spaces,
        )
        value: str | tuple[str, ...] = packed.text
        contributors = set(packed.included_from)
        exclusions, used, capacity = packed.excluded, packed.byte_count, spec.max_bytes
        current: str | tuple[str, ...] = normalize_text(listing.text(backend.field_name))
        unit = f"{used}/{capacity} bytes"
        empty = not packed.included
    else:
        assert spec.max_count is not None and spec.item_max_chars is not None
        slots = pack_keyword_slots(ordered, spec.max_count, spec.item_max_chars, visible=visible)
        value = tuple(s for s in slots.slots if s)
        contributors = {phrase for phrase, _ in slots.placed}
        exclusions, used, capacity = slots.excluded, len(value), spec.max_count
        current = tuple(normalize_text(s) for s in listing.segments(backend.field_name))
        unit = f"{used}/{capacity} slots"
        empty = not slots.placed

    packed_keywords = tuple(s.keyword for s in eligible if s.keyword in contributors)
    retained = tuple(item for item in retained_candidates if item in contributors)
    counts: dict[str, int] = {}
    for item in exclusions:
        counts[item.reason.value] = counts.get(item.reason.value, 0) + 1
    if rule_excluded:
        counts["prohibited_term"] = len(rule_excluded)
    excluded_text = ", ".join(f"{n} {reason}" for reason, n in sorted(counts.items())) or "none"

    def plan(proposal: Proposal | None, note: str) -> BackendPlan:
        return BackendPlan(
            backend.field_name,
            backend.mode,
            proposal,
            packed_keywords,
            exclusions,
            tuple(rule_excluded),
            retained,
            used,
            capacity,
            note,
        )

    if not ranked:
        return plan(None, "no ranked keywords to pack")
    if not packed_keywords:
        return plan(None, f"no ranked keyword could be packed (excluded: {excluded_text})")
    if empty:
        return plan(None, f"nothing could be packed (excluded: {excluded_text})")
    if value == current:
        return plan(None, f"current {backend.field_name} already equals the packed result")
    rationale = (
        f"Packs {len(packed_keywords)} of {len(ranked)} ranked keywords, best first, into "
        f"{backend.field_name} ({unit}). Excluded: {excluded_text}."
    )
    if retained:
        rationale += f" Retains current unscored content: {', '.join(retained)}."
    dropped = [item for item in retained_candidates if item not in contributors]
    if dropped:
        rationale += f" Drops current content: {', '.join(dropped)}."
    proposal = Proposal.create(
        recipe=recipe,
        target_field=backend.field_name,
        value=value,
        rationale=rationale,
        created_at=created_at,
        evidence_ids=_evidence_for(ranked, set(packed_keywords)),
    )
    return plan(proposal, "proposed")


def keyword_recommendations(
    recipe: Recipe,
    listing: Listing,
    ranked: Sequence[KeywordScore],
    *,
    top_n: int,
    backend_plan: BackendPlan | None = None,
) -> tuple[CoverageReport | None, list[Recommendation]]:
    """Coverage of all ranked keywords, plus gap and placement recommendations for the top N."""
    if top_n < 1:
        raise ValueError("top_n must be >= 1")
    if not ranked:
        return None, []
    weights = dict(recipe.coverage_weights)
    coverage = compute_coverage([s.keyword for s in ranked], listing, weights)
    backend_field = recipe.backend.field_name if recipe.backend else None
    visible = sorted(
        (name for name, w in weights.items() if w > 0 and name != backend_field),
        key=lambda name: (-weights[name], name),
    )
    by_keyword = {kc.keyword: kc for kc in coverage.keywords}
    packed = set(backend_plan.packed_keywords) if backend_plan else set()
    proposal_id = backend_plan.proposal.id if backend_plan and backend_plan.proposal else None

    recommendations = []
    for rank, score in enumerate(ranked[:top_n], 1):
        kc = by_keyword[score.keyword]
        blocked = tuple(
            (name, hit.rule_id)
            for name in visible
            if (hit := _prohibiting_rule(recipe, name, score.keyword)) is not None
        )
        blocked_names = {name for name, _ in blocked}
        allowed = tuple(n for n in visible if n not in blocked_names)
        common = {
            "keyword": score.keyword,
            "rank": rank,
            "score": score.score,
            "current_fields": kc.exact_fields,
            "evidence_ids": score.evidence_ids,
            "heuristic_signals": score.heuristic_signals,
            "covered_by_proposal": proposal_id if score.keyword in packed else None,
            "blocked_fields": blocked,
        }
        if not kc.covered:
            recommendations.append(
                Recommendation(
                    kind=RecommendationKind.KEYWORD_GAP,
                    suggested_fields=allowed,
                    reason=(
                        f"Ranked #{rank} (score {score.score:.3f}) but the exact phrase "
                        f"appears in no weighted field."
                    ),
                    **common,
                )
            )
        elif kc.placement_score < 1.0:
            better = tuple(n for n in allowed if weights[n] > weights[kc.best_field])
            if better:
                recommendations.append(
                    Recommendation(
                        kind=RecommendationKind.PLACEMENT_UPGRADE,
                        suggested_fields=better,
                        reason=(
                            f"Ranked #{rank} (score {score.score:.3f}) but found only in "
                            f"{kc.best_field} (placement {kc.placement_score:.2f})."
                        ),
                        **common,
                    )
                )
    return coverage, recommendations


__all__ = [
    "BackendPlan",
    "Recommendation",
    "RecommendationKind",
    "RuleExclusion",
    "keyword_recommendations",
    "plan_backend",
]
