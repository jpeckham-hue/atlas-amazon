"""Research tasks: the mapping from recipe research priorities to provider calls.

Orchestration only. A task decides which provider to call with which
inputs, then stores everything it gets back before anything downstream
reads it. Tasks never score, rank or judge evidence.

Several priorities can map to the same task (e.g. `competitor_titles` and
`competitor_bullets` both need competitor catalog data). The task runs once,
at the first priority that needs it, and later priorities record
`already_done`. Priorities with no offline task are recorded as
`unsupported`, never silently dropped.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from enum import StrEnum

from atlas_amazon.evidence.store import EvidenceStore
from atlas_amazon.keywords.candidates import build_candidates
from atlas_amazon.models import Evidence, EvidenceKind, Listing, ProductInput
from atlas_amazon.recipes.schema import Recipe


class TaskStatus(StrEnum):
    EXECUTED = "executed"
    ALREADY_DONE = "already_done"
    NO_PROVIDER = "no_provider"
    NO_INPUT = "no_input"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True, slots=True)
class TaskRecord:
    priority: str
    task: str | None
    status: TaskStatus
    providers: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    new_records: int = 0
    reused_records: int = 0  # already in the store from an earlier execution of this run
    note: str = ""


@dataclass
class RunContext:
    product: ProductInput
    listing: Listing
    recipe: Recipe
    run_id: str
    seeds: tuple[str, ...]
    listing_phrases: tuple[str, ...]
    providers: object  # ResearchProviders; typed loosely to avoid an import cycle
    store: EvidenceStore
    min_competitor_support: int
    review_limit: int | None
    done: set[str] = field(default_factory=set)

    @property
    def marketplace(self) -> str:
        return self.product.marketplace

    def store_all(self, items: Sequence[Evidence]) -> tuple[tuple[str, ...], int, int]:
        """Persist provider output; returns (ids, new, reused). Idempotent per run."""
        for item in items:
            if item.run_id != self.run_id or item.marketplace != self.marketplace:
                raise ValueError(
                    f"provider returned evidence {item.id} for run {item.run_id!r} / "
                    f"{item.marketplace!r}, expected {self.run_id!r} / {self.marketplace!r}"
                )
        fresh: dict[str, Evidence] = {}
        for item in items:
            if item.id not in self.store and item.id not in fresh:
                fresh[item.id] = item
        self.store.append_many(list(fresh.values()))
        ids = tuple(dict.fromkeys(item.id for item in items))
        return ids, len(fresh), len(ids) - len(fresh)

    def stored(self, kind: EvidenceKind) -> list[Evidence]:
        return self.store.query(run_id=self.run_id, marketplace=self.marketplace, kind=kind)


def _competitor_catalog(ctx: RunContext, priority: str) -> TaskRecord:
    provider = ctx.providers.catalog
    asins = ctx.product.competitor_asins
    if provider is None:
        return TaskRecord(
            priority,
            "competitor_catalog",
            TaskStatus.NO_PROVIDER,
            note="no catalog provider configured",
        )
    if not asins:
        return TaskRecord(
            priority,
            "competitor_catalog",
            TaskStatus.NO_INPUT,
            (provider.name,),
            note="no competitor ASINs in the product input",
        )
    ids, new, reused = ctx.store_all(
        provider.get_items(asins, marketplace=ctx.marketplace, run_id=ctx.run_id)
    )
    return TaskRecord(
        priority,
        "competitor_catalog",
        TaskStatus.EXECUTED,
        (provider.name,),
        ids,
        new,
        reused,
        f"requested {len(asins)} competitor ASINs",
    )


def _search_demand(ctx: RunContext, priority: str) -> TaskRecord:
    suggest, metrics = ctx.providers.suggestions, ctx.providers.keywords
    if suggest is None and metrics is None:
        return TaskRecord(
            priority,
            "search_demand",
            TaskStatus.NO_PROVIDER,
            note="no suggestion or keyword-data provider configured",
        )
    used: list[str] = []
    all_ids: list[str] = []
    new_total = reused_total = 0
    notes = []
    if suggest is not None:
        used.append(suggest.name)
        returned: list[Evidence] = []
        for seed in ctx.seeds:
            returned.extend(
                suggest.suggestions(seed, marketplace=ctx.marketplace, run_id=ctx.run_id)
            )
        ids, new, reused = ctx.store_all(returned)
        all_ids.extend(ids)
        new_total, reused_total = new_total + new, reused_total + reused
        notes.append(f"suggestions for {len(ctx.seeds)} seeds")
    else:
        notes.append("no suggestion provider configured")
    if metrics is not None:
        used.append(metrics.name)
        # Candidates are derived from evidence already stored by this point
        # in the run, so research-priority order matters.
        candidates = build_candidates(
            seeds=ctx.seeds,
            suggestions=ctx.stored(EvidenceKind.AUTOCOMPLETE_SUGGESTION),
            competitors=ctx.stored(EvidenceKind.CATALOG_ITEM),
            listing_phrases=ctx.listing_phrases,
            min_competitor_support=ctx.min_competitor_support,
            stopwords=ctx.recipe.backend.stopwords if ctx.recipe.backend else (),
        )
        keywords = [c.keyword for c in candidates]
        ids, new, reused = ctx.store_all(
            metrics.keyword_metrics(keywords, marketplace=ctx.marketplace, run_id=ctx.run_id)
        )
        all_ids.extend(ids)
        new_total, reused_total = new_total + new, reused_total + reused
        notes.append(f"metrics requested for {len(keywords)} candidates")
    else:
        notes.append("no keyword-data provider configured")
    return TaskRecord(
        priority,
        "search_demand",
        TaskStatus.EXECUTED,
        tuple(used),
        tuple(dict.fromkeys(all_ids)),
        new_total,
        reused_total,
        "; ".join(notes),
    )


def _competitor_reviews(ctx: RunContext, priority: str) -> TaskRecord:
    provider = ctx.providers.reviews
    asins = tuple(
        dict.fromkeys(
            ((ctx.product.asin,) if ctx.product.asin else ()) + ctx.product.competitor_asins
        )
    )
    if provider is None:
        return TaskRecord(
            priority,
            "competitor_reviews",
            TaskStatus.NO_PROVIDER,
            note="no review provider configured",
        )
    if not asins:
        return TaskRecord(
            priority,
            "competitor_reviews",
            TaskStatus.NO_INPUT,
            (provider.name,),
            note="no ASINs to fetch reviews for",
        )
    returned: list[Evidence] = []
    for asin in asins:
        returned.extend(
            provider.reviews(
                asin, marketplace=ctx.marketplace, run_id=ctx.run_id, limit=ctx.review_limit
            )
        )
    ids, new, reused = ctx.store_all(returned)
    return TaskRecord(
        priority,
        "competitor_reviews",
        TaskStatus.EXECUTED,
        (provider.name,),
        ids,
        new,
        reused,
        f"reviews for {len(asins)} ASINs; stored only, theme analysis needs semantic review",
    )


TaskFn = Callable[[RunContext, str], TaskRecord]

TASKS: dict[str, TaskFn] = {
    "competitor_catalog": _competitor_catalog,
    "search_demand": _search_demand,
    "competitor_reviews": _competitor_reviews,
}

PRIORITY_TASKS: dict[str, str] = {
    "competitor_titles": "competitor_catalog",
    "competitor_bullets": "competitor_catalog",
    "comparable_titles": "competitor_catalog",
    "category_attributes": "competitor_catalog",
    "search_term_demand": "search_demand",
    "review_themes": "competitor_reviews",
    "reader_review_themes": "competitor_reviews",
}


def run_priority(ctx: RunContext, priority: str) -> TaskRecord:
    task = PRIORITY_TASKS.get(priority)
    if task is None:
        return TaskRecord(
            priority,
            None,
            TaskStatus.UNSUPPORTED,
            note="no offline research task implements this priority yet",
        )
    if task in ctx.done:
        return TaskRecord(
            priority, task, TaskStatus.ALREADY_DONE, note="satisfied by an earlier priority"
        )
    record = TASKS[task](ctx, priority)
    if record.status is TaskStatus.EXECUTED:
        ctx.done.add(task)
    return record
