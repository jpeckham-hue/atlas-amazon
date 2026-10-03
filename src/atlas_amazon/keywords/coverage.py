"""Keyword coverage of a listing.

For each keyword k (deduplicated by `keyword_key`) and each weighted field f:

* exact(k, f) = 1 if k's folded tokens appear contiguously, in order, inside
  a single segment of f (one bullet, or the whole title), else 0.
* token_fraction(k) = |unique tokens of k found anywhere in the weighted
  fields| / |unique tokens of k|. This is the order-insensitive view, since
  Amazon can match words across fields.
* placement(k) = max over f with exact(k, f) = 1 of w_f / max_g(w_g), else 0.
  A keyword in the most important field scores 1.0. One that appears only in
  a field weighted 0.2 relative to it scores 0.2.

The report aggregates these as plain means over keywords. Each per-keyword
value is kept, so every aggregate can be traced back to the keywords behind it.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

from atlas_amazon.keywords.normalize import dedupe_keywords, fold_plural, keyword_key, tokenize
from atlas_amazon.models import Listing


def contains_phrase(haystack: Sequence[str], needle: Sequence[str]) -> bool:
    """True if `needle` occurs as a contiguous run inside `haystack`."""
    n = len(needle)
    if n == 0:
        return False
    target = tuple(needle)
    return any(tuple(haystack[i : i + n]) == target for i in range(len(haystack) - n + 1))


@dataclass(frozen=True, slots=True)
class KeywordCoverage:
    keyword: str
    key: tuple[str, ...]
    exact_fields: tuple[str, ...]
    token_fraction: float
    placement_score: float
    best_field: str | None

    @property
    def covered(self) -> bool:
        return bool(self.exact_fields)


def _mean(values: Iterable[float]) -> float:
    items = list(values)
    return sum(items) / len(items) if items else 0.0


@dataclass(frozen=True, slots=True)
class CoverageReport:
    keywords: tuple[KeywordCoverage, ...]
    field_weights: Mapping[str, float]

    @property
    def exact_rate(self) -> float:
        """Share of keywords whose exact phrase appears in at least one field."""
        return _mean(1.0 if k.covered else 0.0 for k in self.keywords)

    @property
    def token_rate(self) -> float:
        return _mean(k.token_fraction for k in self.keywords)

    @property
    def placement_score(self) -> float:
        return _mean(k.placement_score for k in self.keywords)

    @property
    def uncovered(self) -> tuple[str, ...]:
        return tuple(k.keyword for k in self.keywords if not k.covered)


def compute_coverage(
    keywords: Iterable[str], listing: Listing, field_weights: Mapping[str, float]
) -> CoverageReport:
    weights = {name: float(w) for name, w in field_weights.items()}
    if any(w < 0 for w in weights.values()):
        raise ValueError("field weights must be non-negative")
    max_weight = max(weights.values(), default=0.0)
    if max_weight <= 0:
        raise ValueError("at least one field weight must be positive")

    folded = {
        name: [[fold_plural(t) for t in tokenize(seg)] for seg in listing.segments(name)]
        for name in weights
    }
    present = {t for segs in folded.values() for seg in segs for t in seg}

    results = []
    for keyword in dedupe_keywords(keywords):
        key = keyword_key(keyword)
        exact = tuple(
            name for name in weights if any(contains_phrase(seg, key) for seg in folded[name])
        )
        unique = set(key)
        best = max(exact, key=lambda name: weights[name], default=None)
        results.append(
            KeywordCoverage(
                keyword=keyword,
                key=key,
                exact_fields=exact,
                token_fraction=len(unique & present) / len(unique),
                placement_score=weights[best] / max_weight if best else 0.0,
                best_field=best,
            )
        )
    return CoverageReport(keywords=tuple(results), field_weights=MappingProxyType(weights))
