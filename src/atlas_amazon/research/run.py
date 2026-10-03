"""ResearchRun: the end-to-end offline research workflow.

Phases. Orchestration lives here; every computation is a domain call.

1. Collect: run the recipe's `research.priorities` in order (see `tasks`).
   All provider output is stored before anything is derived from it.
2. Derive: read this run's evidence back from the store, then:
   build_candidates -> derive_signals -> rank_keywords (v0.2 scoring).
3. Assess: audit_listing on the current listing.
4. Recommend: plan_backend (a concrete proposal) and keyword_recommendations
   (gaps and placement upgrades), then validate_proposal for every
   proposal.

Reproducibility: the same fixtures, recipe version, inputs and
`started_at` give an identical ResearchResult. There is no wall clock and
no randomness. Re-running a run_id on the same store reuses its evidence
instead of duplicating it.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from types import MappingProxyType

from atlas_amazon import __version__
from atlas_amazon.audit.listing import audit_listing
from atlas_amazon.evidence.store import EvidenceStore
from atlas_amazon.jsonvalue import canonical_json
from atlas_amazon.keywords.candidates import KeywordCandidate, build_candidates
from atlas_amazon.keywords.coverage import CoverageReport
from atlas_amazon.keywords.normalize import keyword_key, normalize_text
from atlas_amazon.keywords.scoring import KeywordScore, rank_keywords
from atlas_amazon.keywords.signals import SignalDerivation, derive_signals, reference_terms_for
from atlas_amazon.models import AuditReport, EvidenceKind, Listing, ProductInput
from atlas_amazon.planner.proposal import Proposal, ProposalValidation, validate_proposal
from atlas_amazon.planner.recommend import (
    BackendPlan,
    Recommendation,
    keyword_recommendations,
    plan_backend,
)
from atlas_amazon.providers.base import (
    CatalogProvider,
    KeywordDataProvider,
    ReviewProvider,
    SuggestionProvider,
)
from atlas_amazon.recipes.loader import load_recipe
from atlas_amazon.research.tasks import RunContext, TaskRecord, run_priority


@dataclass(frozen=True, slots=True)
class ResearchProviders:
    catalog: CatalogProvider | None = None
    keywords: KeywordDataProvider | None = None
    suggestions: SuggestionProvider | None = None
    reviews: ReviewProvider | None = None

    def names(self) -> dict[str, str | None]:
        return {
            role: (provider.name if provider is not None else None)
            for role, provider in (
                ("catalog", self.catalog),
                ("keywords", self.keywords),
                ("suggestions", self.suggestions),
                ("reviews", self.reviews),
            )
        }


@dataclass(frozen=True, slots=True)
class ResearchConfig:
    top_n: int = 10  # ranked keywords considered for gap/placement recommendations
    min_competitor_support: int = 2  # competitors that must share a phrase
    review_limit: int | None = None

    def __post_init__(self) -> None:
        if self.top_n < 1 or self.min_competitor_support < 1:
            raise ValueError("top_n and min_competitor_support must be >= 1")


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
class ResearchResult:
    metadata: RunMetadata
    tasks: tuple[TaskRecord, ...]
    evidence: EvidenceSummary
    audit: AuditReport
    candidates: tuple[KeywordCandidate, ...]
    derivations: tuple[SignalDerivation, ...]
    ranked: tuple[KeywordScore, ...]
    coverage: CoverageReport | None
    backend_plan: BackendPlan | None
    recommendations: tuple[Recommendation, ...]
    proposals: tuple[Proposal, ...]
    validations: tuple[ProposalValidation, ...]

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

    def execute(self) -> ResearchResult:
        recipe, product, listing = self.recipe, self.product, self.listing
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
            min_competitor_support=self.config.min_competitor_support,
            review_limit=self.config.review_limit,
        )

        # 1. Collect. Every task stores its evidence before returning.
        tasks = tuple(run_priority(ctx, p) for p in recipe.research_priorities)

        # 2. Derive, from the store only.
        suggestions = ctx.stored(EvidenceKind.AUTOCOMPLETE_SUGGESTION)
        catalog = ctx.stored(EvidenceKind.CATALOG_ITEM)
        metrics = ctx.stored(EvidenceKind.KEYWORD_METRIC)
        reviews = ctx.stored(EvidenceKind.REVIEW_SAMPLE)
        candidates = build_candidates(
            seeds=seeds,
            suggestions=suggestions,
            competitors=catalog,
            listing_phrases=ctx.listing_phrases,
            min_competitor_support=self.config.min_competitor_support,
            stopwords=backend.stopwords if backend else (),
        )
        derivations = derive_signals(
            candidates,
            metrics=metrics,
            competitors=catalog,
            reference_terms=reference_terms_for(product.title, seeds),
        )
        ranked = tuple(
            rank_keywords([d.signals for d in derivations if d.signals], recipe.keyword_weights)
        )

        # 3. Assess.
        audit = audit_listing(listing, recipe)

        # 4. Recommend and validate.
        backend_plan = plan_backend(recipe, listing, ranked, created_at=self.started_at)
        coverage, recommendations = keyword_recommendations(
            recipe, listing, ranked, top_n=self.config.top_n, backend_plan=backend_plan
        )
        proposals = tuple(
            p for p in ((backend_plan.proposal,) if backend_plan else ()) if p is not None
        )
        validations = tuple(
            validate_proposal(p, recipe=recipe, base=listing, evidence=self.store)
            for p in proposals
        )

        all_evidence = suggestions + catalog + metrics + reviews
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
            config=self.config,
            evidence_fingerprint=fingerprint,
        )
        return ResearchResult(
            metadata=metadata,
            tasks=tasks,
            evidence=summary,
            audit=audit,
            candidates=tuple(candidates),
            derivations=tuple(derivations),
            ranked=ranked,
            coverage=coverage,
            backend_plan=backend_plan,
            recommendations=tuple(recommendations),
            proposals=proposals,
            validations=validations,
        )
