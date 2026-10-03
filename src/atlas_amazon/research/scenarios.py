"""Offline research scenarios: inputs plus provider fixture data in one JSON file.

    {
      "name": "...",
      "run_id": "...",
      "started_at": "2026-10-03T09:00:00+00:00",
      "product": {"title": ..., "recipe_id": ..., "marketplace": "US", "asin": ...,
                  "competitor_asins": [...], "attributes": {"seed_keywords": [...]}},
      "listing": {"title": ..., ...},
      "providers": ["catalog", "keywords", "suggestions", "reviews", "review_themes",
                    "judgments"],
      "fixture": { ...providers.fixtures format... }
    }

`providers` lists which fake providers are configured. Leaving one out
simulates a missing data source.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Any

from atlas_amazon.evidence.store import EvidenceStore, InMemoryEvidenceStore
from atlas_amazon.models import Listing, ProductInput
from atlas_amazon.providers.fixtures import (
    FixtureCatalogProvider,
    FixtureData,
    FixtureJudgmentProvider,
    FixtureKeywordDataProvider,
    FixtureReviewProvider,
    FixtureReviewThemeProvider,
    FixtureSuggestionProvider,
)
from atlas_amazon.research.run import ResearchConfig, ResearchProviders, ResearchResult, ResearchRun
from atlas_amazon.semantic.human import HumanJudgmentProvider

_ROLES = {
    "catalog": FixtureCatalogProvider,
    "keywords": FixtureKeywordDataProvider,
    "suggestions": FixtureSuggestionProvider,
    "reviews": FixtureReviewProvider,
    "review_themes": FixtureReviewThemeProvider,
    "judgments": FixtureJudgmentProvider,
    "human_judgments": lambda fixture: HumanJudgmentProvider(fixture.semantic["human_judgments"]),
}
_KEYS = frozenset({"name", "run_id", "started_at", "product", "listing", "providers", "fixture"})


@dataclass(frozen=True, slots=True)
class Scenario:
    name: str
    run_id: str
    started_at: datetime
    product: ProductInput
    listing: Listing
    providers: ResearchProviders

    def with_providers(self, **roles) -> Scenario:
        """A copy with some provider roles replaced (e.g. judgments=LLMJudgmentProvider(...))."""
        return replace(self, providers=replace(self.providers, **roles))

    def run(
        self, store: EvidenceStore | None = None, config: ResearchConfig | None = None
    ) -> ResearchResult:
        return ResearchRun(
            product=self.product,
            listing=self.listing,
            recipe_id=self.product.recipe_id,
            run_id=self.run_id,
            providers=self.providers,
            store=store if store is not None else InMemoryEvidenceStore(),
            started_at=self.started_at,
            config=config,
        ).execute()


def load_scenario(path: str | os.PathLike[str]) -> Scenario:
    path = Path(path)
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    unknown = sorted(set(data) - _KEYS)
    if unknown:
        raise ValueError(f"{path.name}: unknown scenario keys {unknown}")
    fixture = FixtureData.from_dict(data["fixture"], origin=path.name)
    roles = data.get("providers", list(_ROLES))
    bad = sorted(set(roles) - set(_ROLES))
    if bad:
        raise ValueError(f"{path.name}: unknown provider roles {bad}")
    providers = ResearchProviders(**{role: _ROLES[role](fixture) for role in roles})
    product = data["product"]
    return Scenario(
        name=data["name"],
        run_id=data["run_id"],
        started_at=datetime.fromisoformat(data["started_at"]),
        product=ProductInput(
            title=product["title"],
            recipe_id=product["recipe_id"],
            marketplace=product.get("marketplace", "US"),
            asin=product.get("asin"),
            competitor_asins=tuple(product.get("competitor_asins", ())),
            attributes=product.get("attributes", {}),
        ),
        listing=Listing(data["listing"]),
        providers=providers,
    )
