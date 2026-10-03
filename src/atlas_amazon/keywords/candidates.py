"""Keyword candidate set, derived deterministically from evidence and inputs.

Sources, in merge-priority order (the first spelling of a keyword key wins):

1. seed: keywords the user supplied (inputs, not evidence, so no IDs);
2. suggestion: each string in `autocomplete_suggestion` evidence;
3. listing: phrases the current listing already targets in list-shaped
   backend fields (e.g. KDP keyword boxes), included so coverage can be
   compared;
4. competitor: 2- and 3-word phrases shared by at least
   `min_competitor_support` competitor listings (from `catalog_item`
   evidence). A phrase may not start or end with a stopword or consist only
   of digits.

Candidates sharing a plural-folded key are merged. Their sources and
evidence IDs are unioned, so lineage is never lost.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import StrEnum

from atlas_amazon.keywords.normalize import fold_plural, keyword_key, normalize_text, tokenize
from atlas_amazon.models import Evidence, EvidenceKind, Listing

# Words that make poor phrase boundaries ("bottle for", "of the").
EDGE_STOPWORDS = frozenset(
    {"a", "an", "and", "as", "at", "by", "for", "from", "in", "of", "on", "or", "the", "to", "with"}
)
# Catalog payload keys read as competitor listing text.
COMPETITOR_TEXT_FIELDS = ("title", "subtitle", "item_highlights", "bullets", "description")
NGRAM_SIZES = (2, 3)


class CandidateSource(StrEnum):
    SEED = "seed"
    SUGGESTION = "suggestion"
    LISTING = "listing"
    COMPETITOR = "competitor"


@dataclass(frozen=True, slots=True)
class KeywordCandidate:
    keyword: str  # normalized text
    key: tuple[str, ...]
    sources: tuple[CandidateSource, ...]
    evidence_ids: tuple[str, ...]


def competitor_listing(evidence: Evidence) -> Listing:
    """The text fields of a `catalog_item` payload as a Listing."""
    if evidence.kind != EvidenceKind.CATALOG_ITEM:
        raise ValueError(f"expected catalog_item evidence, got {evidence.kind!r}")
    fields = {}
    for name in COMPETITOR_TEXT_FIELDS:
        value = evidence.payload.get(name)
        if isinstance(value, str) or (
            isinstance(value, tuple) and all(isinstance(v, str) for v in value)
        ):
            fields[name] = value
    return Listing(fields)


def _phrases(listing: Listing, stopwords: frozenset[str]) -> dict[tuple[str, ...], str]:
    """Folded key -> first display form, for every eligible n-gram in the listing."""
    found: dict[tuple[str, ...], str] = {}
    for name in listing.fields:
        for segment in listing.segments(name):
            tokens = tokenize(segment)
            for n in NGRAM_SIZES:
                for i in range(len(tokens) - n + 1):
                    gram = tokens[i : i + n]
                    if gram[0] in stopwords or gram[-1] in stopwords:
                        continue
                    if all(t.isdigit() for t in gram):
                        continue
                    found.setdefault(tuple(fold_plural(t) for t in gram), " ".join(gram))
    return found


def shared_competitor_phrases(
    competitors: Sequence[Evidence], *, min_support: int, stopwords: Iterable[str] = ()
) -> list[tuple[str, tuple[str, ...]]]:
    """(phrase, supporting evidence IDs) for phrases in >= min_support competitors."""
    if min_support < 1:
        raise ValueError("min_support must be >= 1")
    stop = EDGE_STOPWORDS | {normalize_text(w) for w in stopwords}
    display: dict[tuple[str, ...], str] = {}
    support: dict[tuple[str, ...], list[str]] = {}
    for evidence in competitors:
        for key, phrase in _phrases(competitor_listing(evidence), stop).items():
            display.setdefault(key, phrase)
            support.setdefault(key, []).append(evidence.id)
    return [(display[key], tuple(ids)) for key, ids in support.items() if len(ids) >= min_support]


def build_candidates(
    *,
    seeds: Sequence[str],
    suggestions: Sequence[Evidence],
    competitors: Sequence[Evidence],
    listing_phrases: Sequence[str] = (),
    min_competitor_support: int = 2,
    stopwords: Iterable[str] = (),
) -> list[KeywordCandidate]:
    merged: dict[tuple[str, ...], tuple[str, list[CandidateSource], list[str]]] = {}

    def add(phrase: str, source: CandidateSource, evidence_ids: Iterable[str]) -> None:
        text = normalize_text(phrase)
        key = keyword_key(text)
        if not key:
            return
        _, sources, ids = merged.setdefault(key, (text, [], []))
        if source not in sources:
            sources.append(source)
        for evidence_id in evidence_ids:
            if evidence_id not in ids:
                ids.append(evidence_id)

    for seed in seeds:
        add(seed, CandidateSource.SEED, ())
    for evidence in suggestions:
        if evidence.kind != EvidenceKind.AUTOCOMPLETE_SUGGESTION:
            raise ValueError(f"expected autocomplete_suggestion evidence, got {evidence.kind!r}")
        for suggestion in evidence.payload.get("suggestions", ()):
            if isinstance(suggestion, str):
                add(suggestion, CandidateSource.SUGGESTION, (evidence.id,))
    for phrase in listing_phrases:
        add(phrase, CandidateSource.LISTING, ())
    for phrase, ids in shared_competitor_phrases(
        competitors, min_support=min_competitor_support, stopwords=stopwords
    ):
        add(phrase, CandidateSource.COMPETITOR, ids)

    return [
        KeywordCandidate(text, key, tuple(sources), tuple(ids))
        for key, (text, sources, ids) in merged.items()
    ]
