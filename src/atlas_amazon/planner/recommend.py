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

**Keyword families.** Ranked keywords are family canonicals. Coverage
counts a family as covered when *any* member phrase appears, so "water
bottle insulated" in a bullet covers the "insulated water bottle" family,
and placement is the best over members. Packing uses the canonical only:
the other members share its words, so packing them separately would waste
space. They are listed as `redundant_members`. Families an entity judgment
flags (brand, author, trademark) are kept out of the backend, citing the
judgment.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
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
    redundant_members: tuple[str, ...]  # family members not packed separately (same words)
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
    family_members: tuple[str, ...] = ()  # every phrase in the keyword's family
    matched_member: str | None = None  # member phrase found in the listing (upgrades)


@dataclass(frozen=True, slots=True)
class FamilyCoverage:
    keyword: str  # family canonical
    members: tuple[str, ...]
    covered: bool
    exact_fields: tuple[str, ...]  # union over members, in field-weight order
    best_field: str | None
    best_member: str | None
    placement_score: float


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
    recipe: Recipe,
    listing: Listing,
    ranked: Sequence[KeywordScore],
    *,
    created_at: datetime,
    families: Mapping[str, Sequence[str]] | None = None,
    blocked: Mapping[str, RuleExclusion] | None = None,
) -> BackendPlan | None:
    """`families`: canonical -> member phrases. `blocked`: canonical -> exclusion (entities)."""
    backend = recipe.backend
    if backend is None:
        return None
    families = families or {}
    blocked = blocked or {}
    spec = recipe.fields[backend.field_name]
    rule_excluded: list[RuleExclusion] = []
    eligible: list[KeywordScore] = []
    for score in ranked:
        hit = blocked.get(score.keyword) or _prohibiting_rule(
            recipe, backend.field_name, score.keyword
        )
        if hit:
            rule_excluded.append(hit)
        else:
            eligible.append(score)
    visible = [listing.text(name) for name in backend.visible_fields]
    # Current backend content is kept at the lowest priority instead of being
    # silently dropped. It is unscored, and the rationale says so.
    # In bytes mode the field is a bag of words; in slots mode each box is a phrase.
    ranked_keys = {s.keyword for s in ranked} | {
        member for s in ranked for member in families.get(s.keyword, ())
    }
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
    redundant = tuple(
        member
        for keyword in packed_keywords
        for member in families.get(keyword, ())
        if member != keyword
    )
    counts: dict[str, int] = {}
    for item in exclusions:
        counts[item.reason.value] = counts.get(item.reason.value, 0) + 1
    for item in rule_excluded:
        kind = "entity_flag" if item.rule_id.startswith("entity_judgment:") else "prohibited_term"
        counts[kind] = counts.get(kind, 0) + 1
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
            redundant,
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
    if redundant:
        rationale += (
            f" Skips {len(redundant)} redundant family member(s) sharing their canonical's "
            f"words: {', '.join(redundant)}."
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


def family_coverage(
    recipe: Recipe,
    listing: Listing,
    keywords: Sequence[str],
    families: Mapping[str, Sequence[str]] | None = None,
) -> tuple[CoverageReport | None, tuple[FamilyCoverage, ...]]:
    """Member-level coverage report plus one family-level summary per keyword."""
    if not keywords:
        return None, ()
    families = families or {}
    weights = dict(recipe.coverage_weights)
    members_of = {k: tuple(families.get(k, (k,))) or (k,) for k in keywords}
    phrases = list(dict.fromkeys(p for k in keywords for p in members_of[k]))
    report = compute_coverage(phrases, listing, weights)
    by_phrase = {kc.keyword: kc for kc in report.keywords}
    field_order = list(weights)
    summaries = []
    for keyword in keywords:
        hits = [by_phrase[p] for p in members_of[keyword] if p in by_phrase]
        best = max(hits, key=lambda kc: kc.placement_score, default=None)
        fields = {f for kc in hits for f in kc.exact_fields}
        covered = any(kc.covered for kc in hits)
        summaries.append(
            FamilyCoverage(
                keyword=keyword,
                members=members_of[keyword],
                covered=covered,
                exact_fields=tuple(f for f in field_order if f in fields),
                best_field=best.best_field if best and covered else None,
                best_member=best.keyword if best and covered else None,
                placement_score=best.placement_score if best else 0.0,
            )
        )
    return report, tuple(summaries)


def keyword_recommendations(
    recipe: Recipe,
    listing: Listing,
    ranked: Sequence[KeywordScore],
    *,
    top_n: int,
    backend_plan: BackendPlan | None = None,
    families: Mapping[str, Sequence[str]] | None = None,
    blocked: Mapping[str, RuleExclusion] | None = None,
) -> tuple[CoverageReport | None, tuple[FamilyCoverage, ...], list[Recommendation]]:
    """Coverage of ranked keyword families, plus gap/placement recommendations for the top N.

    Keywords in `blocked` (entity-flagged: another brand, author or trademark) get no
    recommendation: no listing field may carry them.
    """
    blocked = blocked or {}
    if top_n < 1:
        raise ValueError("top_n must be >= 1")
    if not ranked:
        return None, (), []
    families = families or {}
    weights = dict(recipe.coverage_weights)
    coverage, summaries = family_coverage(recipe, listing, [s.keyword for s in ranked], families)
    backend_field = recipe.backend.field_name if recipe.backend else None
    visible = sorted(
        (name for name, w in weights.items() if w > 0 and name != backend_field),
        key=lambda name: (-weights[name], name),
    )
    by_keyword = {fc.keyword: fc for fc in summaries}
    packed = set(backend_plan.packed_keywords) if backend_plan else set()
    proposal_id = backend_plan.proposal.id if backend_plan and backend_plan.proposal else None

    recommendations = []
    for rank, score in enumerate(ranked[:top_n], 1):
        if score.keyword in blocked:
            continue
        fc = by_keyword[score.keyword]
        field_blocks = tuple(
            (name, hit.rule_id)
            for name in visible
            if (hit := _prohibiting_rule(recipe, name, score.keyword)) is not None
        )
        blocked_names = {name for name, _ in field_blocks}
        allowed = tuple(n for n in visible if n not in blocked_names)
        grouped = len(fc.members) > 1
        common = {
            "keyword": score.keyword,
            "rank": rank,
            "score": score.score,
            "current_fields": fc.exact_fields,
            "evidence_ids": score.evidence_ids,
            "heuristic_signals": score.heuristic_signals,
            "covered_by_proposal": proposal_id if score.keyword in packed else None,
            "blocked_fields": field_blocks,
            "family_members": fc.members,
        }
        if not fc.covered:
            what = (
                f"none of its {len(fc.members)} family phrases appears in any weighted field"
                if grouped
                else "the exact phrase appears in no weighted field"
            )
            recommendations.append(
                Recommendation(
                    kind=RecommendationKind.KEYWORD_GAP,
                    suggested_fields=allowed,
                    reason=f"Ranked #{rank} (score {score.score:.3f}) but {what}.",
                    **common,
                )
            )
        elif fc.placement_score < 1.0:
            better = tuple(n for n in allowed if weights[n] > weights[fc.best_field])
            if better:
                via = f" (as '{fc.best_member}')" if fc.best_member != score.keyword else ""
                recommendations.append(
                    Recommendation(
                        kind=RecommendationKind.PLACEMENT_UPGRADE,
                        suggested_fields=better,
                        reason=(
                            f"Ranked #{rank} (score {score.score:.3f}) but found only in "
                            f"{fc.best_field}{via} (placement {fc.placement_score:.2f})."
                        ),
                        matched_member=fc.best_member,
                        **common,
                    )
                )
    return coverage, summaries, recommendations


__all__ = [
    "BackendPlan",
    "FamilyCoverage",
    "Recommendation",
    "RecommendationKind",
    "RuleExclusion",
    "family_coverage",
    "keyword_recommendations",
    "plan_backend",
]
