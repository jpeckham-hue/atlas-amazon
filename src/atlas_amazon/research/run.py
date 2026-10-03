"""ResearchRun: the end-to-end offline research workflow.

Phases. Orchestration lives here; every computation is a domain call.

1. Collect: run the recipe's `research.priorities` in order (see `tasks`).
   All provider output, review themes included, is stored before anything
   is derived from it.
2. Derive, reading this run's evidence back from the store:
   build_candidates -> group_keyword_families
   -> [equivalence judgments for unconfirmed pairs, if a JudgmentProvider is
      configured -> regroup]
   -> [relevance / intent / entity judgments per family]
   -> derive_signals (judgments where present, explicit heuristic fallback)
   -> rank_keywords (on families).
3. Assess: audit_listing on the current listing; summarize_review_themes.
4. Recommend: plan_backend (a concrete proposal; entity-flagged families are
   excluded) and keyword_recommendations (family-aware gaps and placement
   upgrades), then validate_proposal for every proposal.

Every judgment is stored as Evidence first, then parsed and checked
against what was requested. Invalid or unrequested judgments are reported,
never used.

Reproducibility: the same fixtures, recipe version, inputs and
`started_at` give an identical ResearchResult. There is no wall clock and
no randomness. Re-running a run_id on the same store reuses its evidence.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from types import MappingProxyType

from atlas_amazon import __version__
from atlas_amazon.audit.listing import audit_listing
from atlas_amazon.evidence.store import EvidenceStore
from atlas_amazon.jsonvalue import canonical_json
from atlas_amazon.judgments.contract import (
    BLOCKING_ENTITY_LABELS,
    Judgment,
    JudgmentError,
    JudgmentRequest,
    JudgmentType,
    parse_judgment,
)
from atlas_amazon.keywords.candidates import KeywordCandidate, build_candidates
from atlas_amazon.keywords.coverage import CoverageReport
from atlas_amazon.keywords.families import FamilyGrouping, group_keyword_families
from atlas_amazon.keywords.normalize import keyword_key, normalize_text
from atlas_amazon.keywords.scoring import KeywordScore, rank_keywords
from atlas_amazon.keywords.signals import (
    SignalDerivation,
    derive_signals,
    metric_volumes,
    reference_terms_for,
)
from atlas_amazon.models import AuditReport, EvidenceKind, Listing, ProductInput
from atlas_amazon.planner.proposal import Proposal, ProposalValidation, validate_proposal
from atlas_amazon.planner.recommend import (
    BackendPlan,
    FamilyCoverage,
    Recommendation,
    RuleExclusion,
    keyword_recommendations,
    plan_backend,
)
from atlas_amazon.providers.base import (
    CatalogProvider,
    JudgmentProvider,
    KeywordDataProvider,
    ReviewProvider,
    ReviewThemeProvider,
    SuggestionProvider,
)
from atlas_amazon.recipes.loader import load_recipe
from atlas_amazon.research.tasks import RunContext, TaskRecord, TaskStatus, run_priority
from atlas_amazon.reviews.themes import ThemeReport, summarize_review_themes

KEYWORD_JUDGMENTS = (JudgmentType.RELEVANCE, JudgmentType.INTENT, JudgmentType.ENTITY)


@dataclass(frozen=True, slots=True)
class ResearchProviders:
    catalog: CatalogProvider | None = None
    keywords: KeywordDataProvider | None = None
    suggestions: SuggestionProvider | None = None
    reviews: ReviewProvider | None = None
    review_themes: ReviewThemeProvider | None = None
    judgments: JudgmentProvider | None = None

    def names(self) -> dict[str, str | None]:
        return {
            role: (provider.name if provider is not None else None)
            for role, provider in (
                ("catalog", self.catalog),
                ("keywords", self.keywords),
                ("suggestions", self.suggestions),
                ("reviews", self.reviews),
                ("review_themes", self.review_themes),
                ("judgments", self.judgments),
            )
        }


@dataclass(frozen=True, slots=True)
class ResearchConfig:
    top_n: int = 10  # ranked keywords considered for gap/placement recommendations
    min_competitor_support: int = 2  # competitors that must share a phrase
    review_limit: int | None = None
    keyword_families: bool = True  # group equivalent phrases before ranking
    min_equivalence_confidence: float = 0.7  # for judgment-confirmed family links
    min_theme_count: int = 2  # reviews needed for a theme to count as "repeated"

    def __post_init__(self) -> None:
        if self.top_n < 1 or self.min_competitor_support < 1 or self.min_theme_count < 1:
            raise ValueError("top_n, min_competitor_support and min_theme_count must be >= 1")
        if not 0 <= self.min_equivalence_confidence <= 1:
            raise ValueError("min_equivalence_confidence must be within [0, 1]")


@dataclass(frozen=True, slots=True)
class RunMetadata:
    run_id: str
    started_at: datetime
    atlas_version: str
    recipe_id: str
    recipe_version: str
    recipe_lineage: tuple[str, ...]
    research_priorities: tuple[str, ...]
    marketplace: str
    product_title: str
    asin: str | None
    competitor_asins: tuple[str, ...]
    seeds: tuple[str, ...]
    seeds_source: str  # "seed_keywords attribute" or "product title"
    providers: Mapping[str, str | None]
    config: ResearchConfig
    evidence_fingerprint: str  # sha256 over the sorted evidence IDs this run used


@dataclass(frozen=True, slots=True)
class EvidenceSummary:
    total: int
    by_kind: Mapping[str, int]
    by_provider: Mapping[str, int]
    ids_by_kind: Mapping[str, tuple[str, ...]]
    # Explicit gaps: what was asked for but not returned.
    competitors_without_catalog: tuple[str, ...]
    seeds_without_suggestions: tuple[str, ...]
    candidates_without_metrics: tuple[str, ...]
    asins_without_reviews: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EntityFlag:
    keyword: str  # family canonical
    label: str
    entity: str | None
    judgment_id: str


@dataclass(frozen=True, slots=True)
class ResearchResult:
    metadata: RunMetadata
    tasks: tuple[TaskRecord, ...]
    semantic_tasks: tuple[TaskRecord, ...]
    evidence: EvidenceSummary
    audit: AuditReport
    candidates: tuple[KeywordCandidate, ...]
    families: FamilyGrouping
    judgments: tuple[Judgment, ...]
    invalid_judgments: tuple[tuple[str, str], ...]  # (evidence_id, reason)
    entity_flags: tuple[EntityFlag, ...]
    derivations: tuple[SignalDerivation, ...]
    ranked: tuple[KeywordScore, ...]
    coverage: CoverageReport | None
    family_coverage: tuple[FamilyCoverage, ...]
    backend_plan: BackendPlan | None
    recommendations: tuple[Recommendation, ...]
    proposals: tuple[Proposal, ...]
    validations: tuple[ProposalValidation, ...]
    review_themes: ThemeReport | None

    @property
    def unscored(self) -> tuple[SignalDerivation, ...]:
        return tuple(d for d in self.derivations if not d.scorable)

    def derivation(self, keyword: str) -> SignalDerivation:
        for item in self.derivations:
            if item.keyword == keyword:
                return item
        raise KeyError(keyword)


def _seeds(product: ProductInput) -> tuple[tuple[str, ...], str]:
    raw = product.attributes.get("seed_keywords")
    if raw is None:
        return (normalize_text(product.title),), "product title"
    if isinstance(raw, str) or not all(isinstance(s, str) and s.strip() for s in raw):
        raise ValueError("attributes['seed_keywords'] must be a list of non-empty strings")
    return tuple(dict.fromkeys(normalize_text(s) for s in raw)), "seed_keywords attribute"


class ResearchRun:
    def __init__(
        self,
        *,
        product: ProductInput,
        listing: Listing,
        recipe_id: str,
        run_id: str,
        providers: ResearchProviders,
        store: EvidenceStore,
        started_at: datetime,
        config: ResearchConfig | None = None,
        recipe_search_path: Path | None = None,
    ) -> None:
        if product.recipe_id != recipe_id:
            raise ValueError(
                f"product is for recipe {product.recipe_id!r}, run is for {recipe_id!r}"
            )
        if not run_id:
            raise ValueError("run_id must be non-empty")
        if started_at.utcoffset() is None:
            raise ValueError("started_at must be timezone-aware")
        self.product = product
        self.listing = listing
        self.recipe = load_recipe(recipe_id, recipe_search_path)
        self.run_id = run_id
        self.providers = providers
        self.store = store
        self.started_at = started_at
        self.config = config or ResearchConfig()

    # -- semantic orchestration -------------------------------------------------

    def _judge(
        self, ctx: RunContext, task: str, requests: Sequence[JudgmentRequest]
    ) -> tuple[TaskRecord, list[Judgment], list[tuple[str, str]]]:
        provider = self.providers.judgments
        assert provider is not None
        returned = provider.judge(requests, marketplace=ctx.marketplace, run_id=self.run_id)
        ids, new, reused = ctx.store_all(returned)  # stored before use, valid or not
        wanted = {r.input_hash for r in requests}
        valid: list[Judgment] = []
        invalid: list[tuple[str, str]] = []
        for evidence_id in ids:
            try:
                judgment = parse_judgment(self.store.get(evidence_id))
            except JudgmentError as exc:
                invalid.append((evidence_id, str(exc)))
                continue
            if judgment.input_hash not in wanted:
                invalid.append((evidence_id, "answers a request that was not made"))
                continue
            valid.append(judgment)
        note = f"{len(requests)} requested, {len(valid)} valid judgments"
        if invalid:
            note += f", {len(invalid)} invalid"
        unanswered = len(wanted) - len({j.input_hash for j in valid})
        if unanswered:
            note += f", {unanswered} unanswered (fallbacks apply)"
        record = TaskRecord(
            "semantic", task, TaskStatus.EXECUTED, (provider.name,), ids, new, reused, note
        )
        return record, valid, invalid

    # -- workflow ---------------------------------------------------------------

    def execute(self) -> ResearchResult:
        recipe, product, listing, cfg = self.recipe, self.product, self.listing, self.config
        seeds, seeds_source = _seeds(product)
        backend = recipe.backend
        listing_phrases = (
            listing.segments(backend.field_name) if backend and backend.mode == "slots" else ()
        )
        ctx = RunContext(
            product=product,
            listing=listing,
            recipe=recipe,
            run_id=self.run_id,
            seeds=seeds,
            listing_phrases=tuple(listing_phrases),
            providers=self.providers,
            store=self.store,
            min_competitor_support=cfg.min_competitor_support,
            review_limit=cfg.review_limit,
        )

        # 1. Collect. Every task stores its evidence before returning.
        tasks = tuple(run_priority(ctx, p) for p in recipe.research_priorities)

        # 2. Derive, from the store only.
        suggestions = ctx.stored(EvidenceKind.AUTOCOMPLETE_SUGGESTION)
        catalog = ctx.stored(EvidenceKind.CATALOG_ITEM)
        metrics = ctx.stored(EvidenceKind.KEYWORD_METRIC)
        reviews = ctx.stored(EvidenceKind.REVIEW_SAMPLE)
        themes = ctx.stored(EvidenceKind.REVIEW_THEME)
        candidates = build_candidates(
            seeds=seeds,
            suggestions=suggestions,
            competitors=catalog,
            listing_phrases=ctx.listing_phrases,
            min_competitor_support=cfg.min_competitor_support,
            stopwords=backend.stopwords if backend else (),
        )
        volumes = metric_volumes(metrics)

        def group(equivalence: Sequence[Judgment] = ()) -> FamilyGrouping:
            return group_keyword_families(
                candidates,
                volumes=volumes,
                equivalence=equivalence,
                min_confidence=cfg.min_equivalence_confidence,
                enabled=cfg.keyword_families,
            )

        grouping = group()
        judgments: list[Judgment] = []
        invalid: list[tuple[str, str]] = []
        semantic: list[TaskRecord] = []
        if self.providers.judgments is None:
            semantic.append(
                TaskRecord(
                    "semantic",
                    "judgments",
                    TaskStatus.NO_PROVIDER,
                    note="no judgment provider configured; relevance and intent use the explicit "
                    "heuristic fallback; equivalence candidates stay unconfirmed",
                )
            )
        else:
            if grouping.unconfirmed:
                record, valid, bad = self._judge(
                    ctx,
                    "equivalence_judgments",
                    [JudgmentRequest.equivalence(p.a, p.b) for p in grouping.unconfirmed],
                )
                semantic.append(record)
                judgments += valid
                invalid += bad
                grouping = group([j for j in valid if j.type is JudgmentType.EQUIVALENCE])
            else:
                semantic.append(
                    TaskRecord(
                        "semantic",
                        "equivalence_judgments",
                        TaskStatus.NO_INPUT,
                        note="no unconfirmed equivalence pairs",
                    )
                )
            requests = [
                JudgmentRequest.about_keyword(
                    kind, family.canonical, product_title=product.title, seeds=seeds
                )
                for family in grouping.families
                for kind in KEYWORD_JUDGMENTS
            ]
            if requests:
                record, valid, bad = self._judge(ctx, "keyword_judgments", requests)
                semantic.append(record)
                judgments += valid
                invalid += bad

        derivations = derive_signals(
            grouping.families,
            metrics=metrics,
            competitors=catalog,
            reference_terms=reference_terms_for(product.title, seeds),
            judgments=judgments,
        )
        ranked = tuple(
            rank_keywords([d.signals for d in derivations if d.signals], recipe.keyword_weights)
        )

        # Entity judgments flag families that must stay out of the backend.
        by_canonical = {f.canonical: f for f in grouping.families}
        entity_flags = tuple(
            EntityFlag(j.input["keyword"], j.label, j.result["entity"], j.evidence_id)
            for j in judgments
            if j.type is JudgmentType.ENTITY
            and j.label in BLOCKING_ENTITY_LABELS
            and j.input["keyword"] in by_canonical
        )
        blocked = {
            flag.keyword: RuleExclusion(
                flag.keyword,
                f"entity_judgment:{flag.label}",
                (flag.entity or flag.keyword, flag.judgment_id),
            )
            for flag in entity_flags
        }

        # 3. Assess.
        audit = audit_listing(listing, recipe)
        theme_report = (
            summarize_review_themes(themes, reviews, product=product, min_count=cfg.min_theme_count)
            if themes
            else None
        )

        # 4. Recommend and validate.
        family_phrases = {f.canonical: f.phrases for f in grouping.families}
        backend_plan = plan_backend(
            recipe,
            listing,
            ranked,
            created_at=self.started_at,
            families=family_phrases,
            blocked=blocked,
        )
        coverage, family_cov, recommendations = keyword_recommendations(
            recipe,
            listing,
            ranked,
            top_n=cfg.top_n,
            backend_plan=backend_plan,
            families=family_phrases,
            blocked=blocked,
        )
        proposals = tuple(
            p for p in ((backend_plan.proposal,) if backend_plan else ()) if p is not None
        )
        validations = tuple(
            validate_proposal(p, recipe=recipe, base=listing, evidence=self.store)
            for p in proposals
        )

        judgment_evidence = ctx.stored(EvidenceKind.JUDGMENT)
        all_evidence = suggestions + catalog + metrics + reviews + themes + judgment_evidence
        metric_keys = {keyword_key(str(m.payload.get("keyword", m.subject or ""))) for m in metrics}
        summary = EvidenceSummary(
            total=len(all_evidence),
            by_kind=MappingProxyType(dict(sorted(Counter(e.kind for e in all_evidence).items()))),
            by_provider=MappingProxyType(
                dict(sorted(Counter(e.provider for e in all_evidence).items()))
            ),
            ids_by_kind=MappingProxyType(
                {
                    kind: tuple(e.id for e in all_evidence if e.kind == kind)
                    for kind in sorted({e.kind for e in all_evidence})
                }
            ),
            competitors_without_catalog=tuple(
                a for a in product.competitor_asins if a not in {e.subject for e in catalog}
            ),
            seeds_without_suggestions=tuple(
                s for s in seeds if s not in {e.subject for e in suggestions}
            ),
            candidates_without_metrics=tuple(
                c.keyword for c in candidates if c.key not in metric_keys
            ),
            asins_without_reviews=tuple(
                a
                for a in dict.fromkeys(
                    ((product.asin,) if product.asin else ()) + product.competitor_asins
                )
                if a not in {e.subject for e in reviews}
            ),
        )
        fingerprint = hashlib.sha256(
            canonical_json(sorted(e.id for e in all_evidence)).encode("utf-8")
        ).hexdigest()
        metadata = RunMetadata(
            run_id=self.run_id,
            started_at=self.started_at,
            atlas_version=__version__,
            recipe_id=recipe.id,
            recipe_version=recipe.version,
            recipe_lineage=recipe.lineage,
            research_priorities=recipe.research_priorities,
            marketplace=product.marketplace,
            product_title=product.title,
            asin=product.asin,
            competitor_asins=product.competitor_asins,
            seeds=seeds,
            seeds_source=seeds_source,
            providers=MappingProxyType(self.providers.names()),
            config=cfg,
            evidence_fingerprint=fingerprint,
        )
        return ResearchResult(
            metadata=metadata,
            tasks=tasks,
            semantic_tasks=tuple(semantic),
            evidence=summary,
            audit=audit,
            candidates=tuple(candidates),
            families=grouping,
            judgments=tuple(judgments),
            invalid_judgments=tuple(invalid),
            entity_flags=entity_flags,
            derivations=tuple(derivations),
            ranked=ranked,
            coverage=coverage,
            family_coverage=family_cov,
            backend_plan=backend_plan,
            recommendations=tuple(recommendations),
            proposals=proposals,
            validations=validations,
            review_themes=theme_report,
        )
