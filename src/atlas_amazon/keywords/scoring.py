"""Decomposable keyword scoring.

    score(k) = sum over s of  w_s * x_s(k)

for s in KEYWORD_SIGNALS = relevance, demand, competition, intent,
competitor_coverage, where:

* every input signal is a value in [0, 1] plus the evidence IDs behind it;
* competition is supplied as observed competitiveness (higher = harder) and
  scored inverted, as x = 1 - competition, so every scored signal is
  "higher is better";
* the weights w_s come from the recipe, are non-negative and sum to 1, so
  score(k) is also in [0, 1].

A KeywordScore keeps every term: raw value, scored (normalized) value,
weight, contribution and evidence IDs. `score` is exactly the sum of the
contributions. A signal with no evidence IDs is still scored, but is marked
`heuristic`, so nothing unsupported can pass as evidence-backed.

The `*_signal` helpers turn raw evidence measurements into [0, 1] signals
using the documented transforms. Callers may also build signals directly,
e.g. from an LLM relevance judgment that is itself recorded as evidence.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from atlas_amazon.keywords.coverage import contains_phrase
from atlas_amazon.keywords.normalize import fold_plural, keyword_key, tokenize
from atlas_amazon.models import Listing
from atlas_amazon.recipes.schema import KEYWORD_SIGNALS

INVERTED_SIGNALS = frozenset({"competition"})
_WEIGHT_TOLERANCE = 1e-9


@dataclass(frozen=True, slots=True)
class SignalValue:
    """One normalized signal in [0, 1] and the evidence it was derived from."""

    value: float
    evidence_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if isinstance(self.value, bool) or not isinstance(self.value, int | float):
            raise TypeError("signal value must be a number")
        if not math.isfinite(self.value) or not 0.0 <= self.value <= 1.0:
            raise ValueError(f"signal value must be within [0, 1], got {self.value!r}")
        ids = tuple(self.evidence_ids)
        if any(not isinstance(i, str) or not i for i in ids):
            raise ValueError("evidence IDs must be non-empty strings")
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate evidence IDs in signal")
        object.__setattr__(self, "value", float(self.value))
        object.__setattr__(self, "evidence_ids", ids)


@dataclass(frozen=True, slots=True)
class KeywordSignals:
    keyword: str
    relevance: SignalValue
    demand: SignalValue
    competition: SignalValue
    intent: SignalValue
    competitor_coverage: SignalValue

    def __post_init__(self) -> None:
        if not keyword_key(self.keyword):
            raise ValueError("keyword must contain at least one word")

    def signal(self, name: str) -> SignalValue:
        if name not in KEYWORD_SIGNALS:
            raise KeyError(name)
        return getattr(self, name)


@dataclass(frozen=True, slots=True)
class SignalContribution:
    signal: str
    raw_value: float  # as supplied
    normalized_value: float  # as scored (1 - raw for inverted signals)
    inverted: bool
    weight: float
    contribution: float  # weight * normalized_value
    evidence_ids: tuple[str, ...]

    @property
    def heuristic(self) -> bool:
        """True when no evidence backs this signal."""
        return not self.evidence_ids


@dataclass(frozen=True, slots=True)
class KeywordScore:
    keyword: str
    score: float
    contributions: tuple[SignalContribution, ...]

    def contribution(self, signal: str) -> SignalContribution:
        for item in self.contributions:
            if item.signal == signal:
                return item
        raise KeyError(signal)

    @property
    def weights(self) -> dict[str, float]:
        return {c.signal: c.weight for c in self.contributions}

    @property
    def evidence_ids(self) -> tuple[str, ...]:
        """All evidence behind the score, de-duplicated, in signal order."""
        return tuple(dict.fromkeys(i for c in self.contributions for i in c.evidence_ids))

    @property
    def heuristic_signals(self) -> tuple[str, ...]:
        return tuple(c.signal for c in self.contributions if c.heuristic)


def validate_weights(weights: Mapping[str, float]) -> dict[str, float]:
    if set(weights) != set(KEYWORD_SIGNALS):
        raise ValueError(f"weights must define exactly {list(KEYWORD_SIGNALS)}")
    result = {}
    for name in KEYWORD_SIGNALS:
        value = weights[name]
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise TypeError(f"weight {name!r} must be a number")
        if not math.isfinite(value) or value < 0:
            raise ValueError(f"weight {name!r} must be a finite, non-negative number")
        result[name] = float(value)
    if not math.isclose(sum(result.values()), 1.0, abs_tol=_WEIGHT_TOLERANCE):
        raise ValueError("weights must sum to 1")
    return result


def score_keyword(signals: KeywordSignals, weights: Mapping[str, float]) -> KeywordScore:
    checked = validate_weights(weights)
    contributions = []
    for name in KEYWORD_SIGNALS:
        signal = signals.signal(name)
        inverted = name in INVERTED_SIGNALS
        normalized = 1.0 - signal.value if inverted else signal.value
        contributions.append(
            SignalContribution(
                signal=name,
                raw_value=signal.value,
                normalized_value=normalized,
                inverted=inverted,
                weight=checked[name],
                contribution=checked[name] * normalized,
                evidence_ids=signal.evidence_ids,
            )
        )
    total = math.fsum(c.contribution for c in contributions)
    return KeywordScore(keyword=signals.keyword, score=total, contributions=tuple(contributions))


def rank_keywords(
    candidates: Iterable[KeywordSignals], weights: Mapping[str, float]
) -> list[KeywordScore]:
    """Score and sort by descending score, breaking ties on the keyword's matching key.

    Candidates that share a keyword key (e.g. singular/plural) are rejected,
    so one keyword can't occupy several ranks.
    """
    scored: list[KeywordScore] = []
    seen: dict[tuple[str, ...], str] = {}
    for candidate in candidates:
        key = keyword_key(candidate.keyword)
        if key in seen:
            raise ValueError(f"{candidate.keyword!r} duplicates {seen[key]!r}")
        seen[key] = candidate.keyword
        scored.append(score_keyword(candidate, weights))
    return sorted(scored, key=lambda s: (-s.score, keyword_key(s.keyword), s.keyword))


# ---------------------------------------------------------------------------
# Documented transforms from raw measurements to [0, 1] signals


def log_scaled_signal(
    value: float, ceiling: float, evidence_ids: Sequence[str] = ()
) -> SignalValue:
    """log1p(value) / log1p(ceiling), clamped to [0, 1]. Used for search volume.

    `ceiling` is normally the largest value in the candidate set, so the
    top keyword scores 1.0 and the log damps the long tail.
    """
    if value < 0 or ceiling <= 0:
        raise ValueError("value must be >= 0 and ceiling > 0")
    return SignalValue(min(1.0, math.log1p(value) / math.log1p(ceiling)), tuple(evidence_ids))


def linear_signal(
    value: float, low: float, high: float, evidence_ids: Sequence[str] = ()
) -> SignalValue:
    """(value - low) / (high - low), clamped to [0, 1]."""
    if high <= low:
        raise ValueError("high must be greater than low")
    return SignalValue(min(1.0, max(0.0, (value - low) / (high - low))), tuple(evidence_ids))


def competitor_coverage_signal(
    keyword: str, competitors: Sequence[tuple[str, Listing]]
) -> SignalValue:
    """Share of competitor listings containing the keyword phrase in any segment.

    `competitors` pairs each competitor Listing with the ID of the evidence
    it came from. All of those IDs back the signal, because the denominator
    depends on every competitor examined, not only the ones that matched.
    """
    if not competitors:
        raise ValueError("at least one competitor is required")
    key = keyword_key(keyword)
    hits = 0
    for _evidence_id, listing in competitors:
        segments = (seg for name in listing.fields for seg in listing.segments(name))
        if any(contains_phrase([fold_plural(t) for t in tokenize(seg)], key) for seg in segments):
            hits += 1
    ids = tuple(dict.fromkeys(evidence_id for evidence_id, _ in competitors))
    return SignalValue(hits / len(competitors), ids)
