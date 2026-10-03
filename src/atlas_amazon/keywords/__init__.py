"""Deterministic keyword normalization and coverage."""

from atlas_amazon.keywords.coverage import (
    CoverageReport,
    KeywordCoverage,
    compute_coverage,
    contains_phrase,
)
from atlas_amazon.keywords.normalize import (
    dedupe_keywords,
    fold_plural,
    keyword_key,
    normalize_text,
    tokenize,
)

__all__ = [
    "CoverageReport",
    "KeywordCoverage",
    "compute_coverage",
    "contains_phrase",
    "dedupe_keywords",
    "fold_plural",
    "keyword_key",
    "normalize_text",
    "tokenize",
]
