"""Fixture-backed fake providers for offline tests and development.

A fixture is one JSON document:

    {
      "provider": "fixture",
      "retrieved_at": "2026-10-01T12:00:00+00:00",
      "catalog":         {"US": {"<ASIN>": {...listing payload...}}},
      "keyword_metrics": {"US": {"<keyword>": {...metrics...}}},
      "suggestions":     {"US": {"<seed>": ["suggestion", ...]}},
      "reviews":         {"US": {"<ASIN>": [{...review...}, ...]}}
    }

Every section is optional. Lookups for keywords and seeds use normalized
text, so "Water Bottles!" finds a "water bottles" entry. The output is fully
deterministic: a fixed `retrieved_at`, content-addressed evidence IDs, and
`fixture://` source URLs that point back to the exact fixture entry.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from types import MappingProxyType
from typing import Any

from atlas_amazon.evidence.identity import make_evidence
from atlas_amazon.jsonvalue import freeze
from atlas_amazon.keywords.normalize import normalize_text
from atlas_amazon.models import Evidence, EvidenceKind, is_valid_asin

_SECTIONS = ("catalog", "keyword_metrics", "suggestions", "reviews")
_TOP_KEYS = frozenset({"provider", "retrieved_at", *_SECTIONS})


class FixtureError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class FixtureData:
    provider: str
    retrieved_at: datetime
    sections: Mapping[str, Any]
    origin: str = "inline"

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], origin: str = "inline") -> FixtureData:
        if not isinstance(data, Mapping):
            raise FixtureError("fixture must be a JSON object")
        unknown = sorted(set(data) - _TOP_KEYS)
        if unknown:
            raise FixtureError(f"unknown fixture keys {unknown}")
        provider = data.get("provider")
        if not isinstance(provider, str) or not provider:
            raise FixtureError("fixture 'provider' must be a non-empty string")
        try:
            retrieved_at = datetime.fromisoformat(data.get("retrieved_at", ""))
        except (TypeError, ValueError):
            raise FixtureError("fixture 'retrieved_at' must be an ISO 8601 timestamp") from None
        if retrieved_at.utcoffset() is None:
            raise FixtureError("fixture 'retrieved_at' must include a UTC offset")
        sections = {}
        for name in _SECTIONS:
            section = data.get(name, {})
            if not isinstance(section, Mapping) or not all(
                isinstance(v, Mapping) for v in section.values()
            ):
                raise FixtureError(f"fixture section {name!r} must map marketplace -> object")
            sections[name] = freeze(section, name)
        return cls(provider, retrieved_at, MappingProxyType(sections), origin)

    @classmethod
    def load(cls, path: str | os.PathLike[str]) -> FixtureData:
        path = Path(path)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise FixtureError(f"{path}: invalid JSON: {exc}") from exc
        return cls.from_dict(data, origin=path.name)

    def entries(self, section: str, marketplace: str) -> Mapping[str, Any]:
        return self.sections[section].get(marketplace, MappingProxyType({}))

    def url(self, section: str, marketplace: str, key: str) -> str:
        return f"fixture://{self.origin}#{section}/{marketplace}/{key}"


def _require_marketplace(marketplace: str) -> None:
    if not isinstance(marketplace, str) or not marketplace:
        raise ValueError("marketplace must be a non-empty string")


def _normalized_lookup(entries: Mapping[str, Any]) -> dict[str, tuple[str, Any]]:
    """normalized key -> (original key, value). Fails if two keys normalize alike."""
    table: dict[str, tuple[str, Any]] = {}
    for key, value in entries.items():
        norm = normalize_text(key)
        if norm in table:
            raise FixtureError(f"fixture keys {table[norm][0]!r} and {key!r} collide")
        table[norm] = (key, value)
    return table


class _FixtureProvider:
    def __init__(self, fixture: FixtureData) -> None:
        self.fixture = fixture
        self.name = fixture.provider

    def _evidence(
        self,
        *,
        kind: EvidenceKind,
        section: str,
        marketplace: str,
        key: str,
        subject: str,
        payload: Mapping[str, Any],
        run_id: str | None,
    ) -> Evidence:
        return make_evidence(
            provider=self.name,
            kind=kind,
            marketplace=marketplace,
            retrieved_at=self.fixture.retrieved_at,
            payload=payload,
            subject=subject,
            run_id=run_id,
            source_url=self.fixture.url(section, marketplace, key),
        )


class FixtureCatalogProvider(_FixtureProvider):
    def get_items(
        self, asins: Sequence[str], *, marketplace: str, run_id: str | None = None
    ) -> list[Evidence]:
        _require_marketplace(marketplace)
        entries = self.fixture.entries("catalog", marketplace)
        result = []
        for asin in dict.fromkeys(asins):
            if not is_valid_asin(asin):
                raise ValueError(f"invalid ASIN: {asin!r}")
            if asin in entries:
                if not isinstance(entries[asin], Mapping):
                    raise FixtureError(f"catalog entry {asin!r} must be an object")
                result.append(
                    self._evidence(
                        kind=EvidenceKind.CATALOG_ITEM,
                        section="catalog",
                        marketplace=marketplace,
                        key=asin,
                        subject=asin,
                        payload=entries[asin],
                        run_id=run_id,
                    )
                )
        return result


class FixtureKeywordDataProvider(_FixtureProvider):
    def keyword_metrics(
        self, keywords: Sequence[str], *, marketplace: str, run_id: str | None = None
    ) -> list[Evidence]:
        _require_marketplace(marketplace)
        table = _normalized_lookup(self.fixture.entries("keyword_metrics", marketplace))
        result = []
        for norm in dict.fromkeys(normalize_text(k) for k in keywords):
            if norm in table:
                key, metrics = table[norm]
                if not isinstance(metrics, Mapping):
                    raise FixtureError(f"keyword_metrics entry {key!r} must be an object")
                result.append(
                    self._evidence(
                        kind=EvidenceKind.KEYWORD_METRIC,
                        section="keyword_metrics",
                        marketplace=marketplace,
                        key=key,
                        subject=norm,
                        payload={"keyword": norm, **metrics},
                        run_id=run_id,
                    )
                )
        return result


class FixtureSuggestionProvider(_FixtureProvider):
    def suggestions(
        self, seed: str, *, marketplace: str, run_id: str | None = None
    ) -> list[Evidence]:
        _require_marketplace(marketplace)
        norm = normalize_text(seed)
        table = _normalized_lookup(self.fixture.entries("suggestions", marketplace))
        if not norm or norm not in table:
            return []
        key, suggestions = table[norm]
        if not isinstance(suggestions, tuple) or not all(isinstance(s, str) for s in suggestions):
            raise FixtureError(f"suggestions entry {key!r} must be a list of strings")
        payload = {"seed": norm, "suggestions": list(suggestions)}
        return [
            self._evidence(
                kind=EvidenceKind.AUTOCOMPLETE_SUGGESTION,
                section="suggestions",
                marketplace=marketplace,
                key=key,
                subject=norm,
                payload=payload,
                run_id=run_id,
            )
        ]


class FixtureReviewProvider(_FixtureProvider):
    def reviews(
        self,
        asin: str,
        *,
        marketplace: str,
        run_id: str | None = None,
        limit: int | None = None,
    ) -> list[Evidence]:
        _require_marketplace(marketplace)
        if not is_valid_asin(asin):
            raise ValueError(f"invalid ASIN: {asin!r}")
        if limit is not None and (isinstance(limit, bool) or limit < 0):
            raise ValueError("limit must be a non-negative integer")
        samples = self.fixture.entries("reviews", marketplace).get(asin, ())
        if not isinstance(samples, tuple) or not all(isinstance(r, Mapping) for r in samples):
            raise FixtureError(f"reviews entry {asin!r} must be a list of objects")
        if limit is not None:
            samples = samples[:limit]
        return [
            self._evidence(
                kind=EvidenceKind.REVIEW_SAMPLE,
                section="reviews",
                marketplace=marketplace,
                key=f"{asin}/{index}",
                subject=asin,
                payload={"asin": asin, "index": index, **review},
                run_id=run_id,
            )
            for index, review in enumerate(samples)
        ]
