"""Provider boundaries. Providers return Evidence records, never raw dicts."""

from atlas_amazon.providers.base import (
    CatalogProvider,
    KeywordDataProvider,
    ReviewProvider,
    SuggestionProvider,
)
from atlas_amazon.providers.fixtures import (
    FixtureCatalogProvider,
    FixtureData,
    FixtureError,
    FixtureKeywordDataProvider,
    FixtureReviewProvider,
    FixtureSuggestionProvider,
)

__all__ = [
    "CatalogProvider",
    "FixtureCatalogProvider",
    "FixtureData",
    "FixtureError",
    "FixtureKeywordDataProvider",
    "FixtureReviewProvider",
    "FixtureSuggestionProvider",
    "KeywordDataProvider",
    "ReviewProvider",
    "SuggestionProvider",
]
