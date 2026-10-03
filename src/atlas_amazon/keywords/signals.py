"""Derive v0.2 scoring signals for keyword candidates from stored evidence.

Evidence-derived (each SignalValue cites the evidence it came from):

* demand = log1p(search_volume) / log1p(max search_volume over the
  candidates' metrics), from `keyword_metric` evidence;
* competition = the metric's `competition` value in [0, 1] (scored
  inverted by `score_keyword`);
* competitor_coverage = the share of competitor listings containing the
  exact phrase (`catalog_item` evidence).

Heuristic placeholders (v0.3; no evidence IDs, so `score_keyword` flags them):

* relevance = the share of the keyword's non-stopword terms that appear in
  the product title or seed keywords;
* intent = a specificity proxy, min(1, words / 4). Longer phrases tend to
  express narrower purchase intent.

**Missing data is never filled in.** A candidate missing any evidence-derived
signal gets `signals=None`, and `missing` and `notes` say exactly what is
absent. Callers report such candidates as unscored instead of ranking them
on invented values.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

from atlas_amazon.keywords.candidates import EDGE_STOPWORDS, KeywordCandidate, competitor_listing
from atlas_amazon.keywords.normalize import fold_plural, keyword_key, normalize_text, tokenize
from atlas_amazon.keywords.scoring import (
    KeywordSignals,
    SignalValue,
    competitor_coverage_signal,
    log_scaled_signal,
)
from atlas_amazon.models import Evidence, EvidenceKind

EVIDENCE_SIGNALS = ("demand", "competition", "competitor_coverage")
HEURISTIC_SIGNALS = ("relevance", "intent")
INTENT_FULL_WORDS = 4


@dataclass(frozen=True, slots=True)
class SignalDerivation:
    candidate: KeywordCandidate
    signals: KeywordSignals | None  # None when any evidence-derived signal is missing
    missing: tuple[str, ...]
    notes: Mapping[str, str]  # signal -> how it was derived, or why it is missing

    @property
    def keyword(self) -> str:
        return self.candidate.keyword

    @property
    def scorable(self) -> bool:
        return self.signals is not None


def _valid_volume(value: object) -> bool:
    return (
        isinstance(value, int | float)
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value >= 0
    )


def _valid_fraction(value: object) -> bool:
    return _valid_volume(value) and value <= 1  # type: ignore[operator]


def _metric_index(
    metrics: Sequence[Evidence],
) -> tuple[dict[tuple[str, ...], Evidence], dict[tuple[str, ...], tuple[str, ...]]]:
    """key -> first metric evidence, plus key -> IDs of ignored duplicate metrics."""
    index: dict[tuple[str, ...], Evidence] = {}
    duplicates: dict[tuple[str, ...], list[str]] = {}
    for evidence in metrics:
        if evidence.kind != EvidenceKind.KEYWORD_METRIC:
            raise ValueError(f"expected keyword_metric evidence, got {evidence.kind!r}")
        keyword = evidence.payload.get("keyword", evidence.subject or "")
        key = keyword_key(keyword if isinstance(keyword, str) else "")
        if not key:
            continue
        if key in index:
            duplicates.setdefault(key, []).append(evidence.id)
        else:
            index[key] = evidence
    return index, {k: tuple(v) for k, v in duplicates.items()}


def heuristic_relevance(keyword: str, reference_terms: Iterable[str]) -> tuple[float, str]:
    reference = {fold_plural(t) for text in reference_terms for t in tokenize(text)}
    terms = [t for t in dict.fromkeys(tokenize(keyword)) if t not in EDGE_STOPWORDS]
    if not terms:
        return 0.0, "heuristic: keyword has no non-stopword terms"
    hits = sum(1 for t in terms if fold_plural(t) in reference)
    return hits / len(terms), (
        f"heuristic: {hits}/{len(terms)} keyword terms appear in the product title/seed keywords"
    )


def heuristic_intent(keyword: str) -> tuple[float, str]:
    words = len(tokenize(keyword))
    value = min(1.0, words / INTENT_FULL_WORDS)
    return value, f"heuristic: specificity proxy min(1, {words} words / {INTENT_FULL_WORDS})"


def derive_signals(
    candidates: Sequence[KeywordCandidate],
    *,
    metrics: Sequence[Evidence],
    competitors: Sequence[Evidence],
    reference_terms: Sequence[str],
) -> list[SignalDerivation]:
    index, duplicates = _metric_index(metrics)
    matched = [index[c.key] for c in candidates if c.key in index]
    volumes = [m.payload.get("search_volume") for m in matched]
    ceiling = max((v for v in volumes if _valid_volume(v)), default=None)
    competitor_pairs = [(e.id, competitor_listing(e)) for e in competitors]

    results = []
    for candidate in candidates:
        notes: dict[str, str] = {}
        values: dict[str, SignalValue] = {}
        metric = index.get(candidate.key)
        dup_note = (
            f" (ignored duplicate metrics {list(duplicates[candidate.key])})"
            if candidate.key in duplicates
            else ""
        )

        if metric is None:
            notes["demand"] = notes["competition"] = "missing: no keyword_metric evidence"
        else:
            volume = metric.payload.get("search_volume")
            if not _valid_volume(volume):
                notes["demand"] = f"missing: {metric.id} has no valid search_volume"
            elif ceiling:
                values["demand"] = log_scaled_signal(volume, ceiling, [metric.id])
                notes["demand"] = f"log1p({volume}) / log1p({ceiling}) from {metric.id}{dup_note}"
            else:
                values["demand"] = SignalValue(0.0, (metric.id,))
                notes["demand"] = f"search_volume 0 and ceiling 0 from {metric.id}{dup_note}"
            competition = metric.payload.get("competition")
            if _valid_fraction(competition):
                values["competition"] = SignalValue(competition, (metric.id,))
                notes["competition"] = (
                    f"competition {competition} from {metric.id}, scored as 1 - value{dup_note}"
                )
            else:
                notes["competition"] = f"missing: {metric.id} has no competition value in [0, 1]"

        if competitor_pairs:
            coverage = competitor_coverage_signal(candidate.keyword, competitor_pairs)
            values["competitor_coverage"] = coverage
            hits = round(coverage.value * len(competitor_pairs))
            notes["competitor_coverage"] = (
                f"{hits}/{len(competitor_pairs)} competitor listings contain the phrase"
            )
        else:
            notes["competitor_coverage"] = "missing: no competitor catalog_item evidence"

        relevance, notes["relevance"] = heuristic_relevance(candidate.keyword, reference_terms)
        intent, notes["intent"] = heuristic_intent(candidate.keyword)
        values["relevance"] = SignalValue(relevance)
        values["intent"] = SignalValue(intent)

        missing = tuple(name for name in EVIDENCE_SIGNALS if name not in values)
        signals = None
        if not missing:
            signals = KeywordSignals(keyword=candidate.keyword, **values)
        results.append(SignalDerivation(candidate, signals, missing, MappingProxyType(notes)))
    return results


def reference_terms_for(product_title: str, seeds: Sequence[str]) -> tuple[str, ...]:
    return tuple(normalize_text(t) for t in (product_title, *seeds) if normalize_text(t))
