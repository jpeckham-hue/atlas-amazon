"""Narrow provider protocols.

Each protocol does one job and returns `Evidence` with a fixed `kind`.
Live adapters (SP-API, keyword vendors, autocomplete, review vendors) will
implement these later. The domain layer only ever sees the protocol.

Shared conventions:

* `marketplace` is required. Evidence is always marketplace-scoped.
* `run_id` is stamped on every record, so one research run's evidence can
  be retrieved together.
* Asking about something the provider has no data for returns no evidence
  for it, not an error. Missing data stays visible as absence, never as an
  invented default.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from atlas_amazon.judgments.contract import JudgmentRequest
from atlas_amazon.models import Evidence


@runtime_checkable
class CatalogProvider(Protocol):
    """Listing content and catalog attributes for ASINs. Kind: `catalog_item`."""

    name: str

    def get_items(
        self, asins: Sequence[str], *, marketplace: str, run_id: str | None = None
    ) -> list[Evidence]: ...


@runtime_checkable
class CatalogSearchProvider(Protocol):
    """Catalog items matching keyword queries (market data, not demand).

    Kinds: `catalog_search` (one per query: the returned ASINs in order) and
    `catalog_item` (one per returned item). The returned order is the catalog's,
    not shopper search rank, and carries no search volume.
    """

    name: str
    is_live: bool

    def search(
        self, keywords: Sequence[str], *, marketplace: str, run_id: str | None = None
    ) -> list[Evidence]: ...


@runtime_checkable
class KeywordDataProvider(Protocol):
    """Search volume and competition metrics for keywords. Kind: `keyword_metric`."""

    name: str

    def keyword_metrics(
        self, keywords: Sequence[str], *, marketplace: str, run_id: str | None = None
    ) -> list[Evidence]: ...


@runtime_checkable
class SuggestionProvider(Protocol):
    """Search-box suggestions for a seed query. Kind: `autocomplete_suggestion`."""

    name: str

    def suggestions(
        self, seed: str, *, marketplace: str, run_id: str | None = None
    ) -> list[Evidence]: ...


@runtime_checkable
class ReviewProvider(Protocol):
    """Customer review samples for an ASIN. Kind: `review_sample`, one per review."""

    name: str

    def reviews(
        self,
        asin: str,
        *,
        marketplace: str,
        run_id: str | None = None,
        limit: int | None = None,
    ) -> list[Evidence]: ...


@runtime_checkable
class ReviewThemeProvider(Protocol):
    """Themes over stored review evidence. Kind: `review_theme`.

    Receives the review_sample Evidence to summarize and must cite those
    records' IDs (see `reviews.review_theme_evidence`).
    """

    name: str

    def themes(
        self, reviews: Sequence[Evidence], *, marketplace: str, run_id: str | None = None
    ) -> list[Evidence]: ...


@runtime_checkable
class JudgmentProvider(Protocol):
    """Semantic judgments (relevance, intent, entity, equivalence). Kind: `judgment`.

    Returns at most one Evidence per request, built with
    `judgments.judgment_evidence`. A request it cannot answer gets no
    evidence, never a default.
    """

    name: str

    def judge(
        self, requests: Sequence[JudgmentRequest], *, marketplace: str, run_id: str | None = None
    ) -> list[Evidence]: ...
