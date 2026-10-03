"""Provider boundaries. Providers return Evidence records, never raw dicts."""

from atlas_amazon.providers.base import (
    CatalogProvider,
    JudgmentProvider,
    KeywordDataProvider,
    ReviewProvider,
    ReviewThemeProvider,
    SuggestionProvider,
)
from atlas_amazon.providers.fixtures import (
    FixtureCatalogProvider,
    FixtureData,
    FixtureError,
    FixtureJudgmentProvider,
    FixtureKeywordDataProvider,
    FixtureReviewProvider,
    FixtureReviewThemeProvider,
    FixtureSuggestionProvider,
)

__all__ = [
    "CatalogProvider",
    "FixtureCatalogProvider",
    "FixtureData",
    "FixtureError",
    "FixtureJudgmentProvider",
    "FixtureKeywordDataProvider",
    "FixtureReviewProvider",
    "FixtureReviewThemeProvider",
    "FixtureSuggestionProvider",
    "JudgmentProvider",
    "KeywordDataProvider",
    "ReviewProvider",
    "ReviewThemeProvider",
    "SuggestionProvider",
]
