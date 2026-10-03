"""Derive v0.2 scoring signals for keyword families from stored evidence.

Ranking works on families, so each family gets one KeywordSignals labeled
with its canonical phrase. Aggregation never counts the same evidence twice:

* demand = log1p(V) / log1p(max V over families). V is the sum of the
  family members' search volumes, each `keyword_metric` evidence counted
  once (members are distinct queries).
* competition = the volume-weighted mean of members' `competition` (a plain
  mean if total volume is 0), scored inverted by `score_keyword`.
* competitor_coverage = the share of competitor listings containing **any**
  member phrase. Each competitor counts once, however many members it
  contains.

Relevance and intent have one of two sources, recorded per signal:

* `judgment`: a validated `judgment` Evidence for the canonical phrase (or
  failing that, for the first member that has one). The signal cites that
  evidence.
* `heuristic` (explicit fallback): the v0.3 formulas. Share of the canonical
  phrase's non-stopword terms found in the product title or seeds;
  specificity min(1, words/4). These cite no evidence, so `score_keyword`
  flags them.

**Missing data is never filled in.** A family missing any evidence-derived
signal gets `signals=None`, with per-signal reasons, and is reported as
unscored.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from atlas_amazon.judgments.contract import Judgment, JudgmentType
from atlas_amazon.keywords.candidates import EDGE_STOPWORDS, competitor_listing
from atlas_amazon.keywords.coverage import contains_phrase
from atlas_amazon.keywords.families import KeywordFamily
from atlas_amazon.keywords.normalize import fold_plural, keyword_key, normalize_text, tokenize
from atlas_amazon.keywords.scoring import KeywordSignals, SignalValue, log_scaled_signal
from atlas_amazon.models import Evidence, EvidenceKind

EVIDENCE_SIGNALS = ("demand", "competition", "competitor_coverage")
SEMANTIC_SIGNALS = ("relevance", "intent")
INTENT_FULL_WORDS = 4


class SignalSource(StrEnum):
    EVIDENCE = "evidence"  # measured provider data (metrics, catalog)
    JUDGMENT = "judgment"  # a recorded semantic judgment (model or rule)
    HEURISTIC = "heuristic"  # deterministic placeholder; no evidence
    HUMAN = "human"  # a human reviewer's judgment (overrides model judgments)


@dataclass(frozen=True, slots=True)
class SignalDerivation:
    family: KeywordFamily
    signals: KeywordSignals | None  # None when any evidence-derived signal is missing
    missing: tuple[str, ...]
    notes: Mapping[str, str]  # signal -> how it was derived, or why it is missing
    sources: Mapping[str, SignalSource]  # signal -> source, for every derived signal
    intent_label: str | None = None  # from an intent judgment, when used

    @property
    def keyword(self) -> str:
        return self.family.canonical

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


def metric_index(
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


def metric_volumes(metrics: Sequence[Evidence]) -> dict[tuple[str, ...], float]:
    """key -> valid search volume, for choosing canonical family labels."""
    index, _ = metric_index(metrics)
    return {
        key: float(ev.payload["search_volume"])
        for key, ev in index.items()
        if _valid_volume(ev.payload.get("search_volume"))
    }


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


def _folded_segments(evidence: Evidence) -> list[list[str]]:
    listing = competitor_listing(evidence)
    return [
        [fold_plural(t) for t in tokenize(seg)]
        for name in listing.fields
        for seg in listing.segments(name)
    ]


def _judgment_for(
    family: KeywordFamily, kind: JudgmentType, index: Mapping[tuple[str, str], Judgment]
) -> tuple[Judgment | None, str]:
    for phrase in (family.canonical, *[p for p in family.phrases if p != family.canonical]):
        judgment = index.get((kind.value, phrase))
        if judgment is not None:
            return judgment, phrase
    return None, ""


def _judged_note(judgment: Judgment, phrase: str, family: KeywordFamily) -> str:
    about = "" if phrase == family.canonical else f" (judged on member '{phrase}')"
    conf = "n/a" if judgment.confidence is None else f"{judgment.confidence:g}"
    return (
        f"judgment {judgment.evidence_id}: {judgment.model} / {judgment.prompt_version}, "
        f"confidence {conf}{about}: {judgment.rationale}"
    )


def derive_signals(
    families: Sequence[KeywordFamily],
    *,
    metrics: Sequence[Evidence],
    competitors: Sequence[Evidence],
    reference_terms: Sequence[str],
    judgments: Sequence[Judgment] = (),
) -> list[SignalDerivation]:
    index, duplicates = metric_index(metrics)
    judged: dict[tuple[str, str], Judgment] = {}
    for j in judgments:
        if j.type in (JudgmentType.RELEVANCE, JudgmentType.INTENT):
            judged.setdefault((j.type.value, j.input["keyword"]), j)
    competitor_segments = [(e.id, _folded_segments(e)) for e in competitors]

    def family_metrics(family: KeywordFamily) -> list[tuple[str, Evidence]]:
        found: dict[str, tuple[str, Evidence]] = {}
        for member in family.members:
            ev = index.get(member.key)
            if ev is not None and ev.id not in found:
                found[ev.id] = (member.keyword, ev)
        return list(found.values())

    volumes = {}
    for family in families:
        valid = [
            ev.payload["search_volume"]
            for _, ev in family_metrics(family)
            if _valid_volume(ev.payload.get("search_volume"))
        ]
        if valid:
            volumes[family.id] = sum(valid)
    ceiling = max(volumes.values(), default=None)

    results = []
    for family in families:
        notes: dict[str, str] = {}
        sources: dict[str, SignalSource] = {}
        values: dict[str, SignalValue] = {}
        fm = family_metrics(family)
        without = [m.keyword for m in family.members if m.key not in index]
        dup = [i for m in family.members for i in duplicates.get(m.key, ())]
        extra = (f"; members without metrics: {without}" if without and fm else "") + (
            f"; ignored duplicate metrics {dup}" if dup else ""
        )

        # demand
        vol_items = [(p, ev) for p, ev in fm if _valid_volume(ev.payload.get("search_volume"))]
        if not fm:
            notes["demand"] = notes["competition"] = "missing: no keyword_metric evidence"
        else:
            if not vol_items:
                notes["demand"] = f"missing: no valid search_volume in {[e.id for _, e in fm]}"
            else:
                total = volumes[family.id]
                ids = [ev.id for _, ev in vol_items]
                parts = " + ".join(f"{ev.payload['search_volume']}" for _, ev in vol_items)
                shown = f"{parts} = {total}" if len(vol_items) > 1 else f"{total}"
                if ceiling:
                    values["demand"] = log_scaled_signal(total, ceiling, ids)
                    notes["demand"] = f"log1p({shown}) / log1p({ceiling}) from {ids}{extra}"
                else:
                    values["demand"] = SignalValue(0.0, tuple(ids))
                    notes["demand"] = f"search_volume 0 and ceiling 0 from {ids}{extra}"
                sources["demand"] = SignalSource.EVIDENCE
            # competition
            comp_items = [(p, ev) for p, ev in fm if _valid_fraction(ev.payload.get("competition"))]
            if not comp_items:
                notes["competition"] = (
                    f"missing: no competition value in [0, 1] in {[e.id for _, e in fm]}"
                )
            else:
                weights = [ev.payload.get("search_volume") for _, ev in comp_items]
                if all(_valid_volume(w) for w in weights) and sum(weights) > 0:
                    value = sum(
                        w * ev.payload["competition"]
                        for w, (_, ev) in zip(weights, comp_items, strict=True)
                    ) / sum(weights)
                    how = "volume-weighted mean" if len(comp_items) > 1 else "competition"
                else:
                    value = sum(ev.payload["competition"] for _, ev in comp_items) / len(comp_items)
                    how = "mean" if len(comp_items) > 1 else "competition"
                ids = tuple(ev.id for _, ev in comp_items)
                values["competition"] = SignalValue(min(1.0, max(0.0, value)), ids)
                notes["competition"] = (
                    f"{how} {value:.3f} from {list(ids)}, scored as 1 - value{extra}"
                )
                sources["competition"] = SignalSource.EVIDENCE

        # competitor coverage
        if competitor_segments:
            keys = [m.key for m in family.members]
            hits = [
                cid
                for cid, segs in competitor_segments
                if any(contains_phrase(seg, key) for seg in segs for key in keys)
            ]
            ids = tuple(dict.fromkeys(cid for cid, _ in competitor_segments))
            values["competitor_coverage"] = SignalValue(len(hits) / len(competitor_segments), ids)
            scope = "the phrase" if len(keys) == 1 else f"any of {len(keys)} member phrases"
            notes["competitor_coverage"] = (
                f"{len(hits)}/{len(competitor_segments)} competitor listings contain {scope}"
            )
            sources["competitor_coverage"] = SignalSource.EVIDENCE
        else:
            notes["competitor_coverage"] = "missing: no competitor catalog_item evidence"

        # relevance and intent: judgment first, explicit heuristic fallback
        intent_label = None
        for name, kind in (("relevance", JudgmentType.RELEVANCE), ("intent", JudgmentType.INTENT)):
            judgment, phrase = _judgment_for(family, kind, judged)
            if judgment is not None:
                values[name] = SignalValue(judgment.score, (judgment.evidence_id,))
                notes[name] = _judged_note(judgment, phrase, family)
                sources[name] = SignalSource.HUMAN if judgment.is_human else SignalSource.JUDGMENT
                if kind is JudgmentType.INTENT:
                    intent_label = judgment.label
            else:
                value, notes[name] = (
                    heuristic_relevance(family.canonical, reference_terms)
                    if kind is JudgmentType.RELEVANCE
                    else heuristic_intent(family.canonical)
                )
                values[name] = SignalValue(value)
                sources[name] = SignalSource.HEURISTIC

        missing = tuple(name for name in EVIDENCE_SIGNALS if name not in values)
        signals = None
        if not missing:
            signals = KeywordSignals(keyword=family.canonical, **values)
        results.append(
            SignalDerivation(
                family,
                signals,
                missing,
                MappingProxyType(notes),
                MappingProxyType(sources),
                intent_label,
            )
        )
    return results


def reference_terms_for(product_title: str, seeds: Sequence[str]) -> tuple[str, ...]:
    return tuple(normalize_text(t) for t in (product_title, *seeds) if normalize_text(t))
