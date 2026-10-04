"""Review themes.

A theme is recorded as `review_theme` Evidence:

    payload = {
      "theme": "lid leaks",
      "polarity": "positive" | "negative" | "mixed" | "neutral",
      "review_evidence_ids": [...],   # the review_sample evidence it summarizes
      "products": [ASIN, ...],        # sorted unique ASINs of those reviews
      "count": n,                     # == len(review_evidence_ids)
      "terms": ["leak", "lid"],       # phrases used to relate the theme to features
      "extractor": "...", "extractor_version": "...", "rationale": "...",
    }

`parse_review_theme` re-derives `products` and `count` from the referenced
reviews, so a theme can't overstate its support.

`summarize_review_themes` is deterministic and makes **no claims about our
product**:

* positives / complaints: themes with count >= min_count, by polarity;
* opportunities: repeated competitor complaints and praise, phrased
  conditionally ("if your product ..."). First-party support is always a
  verbatim entry of `ProductInput.attributes["features"]`; nothing else is
  ever cited as a product fact. A feature supports a theme when (v0.8):

  1. one of the theme's terms appears in it as a phrase; or
  2. it shares at least `MIN_SHARED_WORDS` distinctive words with the theme's
     label and terms; or
  3. it shares one such word, plus one more word that recurs across the
     theme's supporting reviews (in at least two of them).

  "Distinctive" excludes connecting words, generic filler and the words of
  the product's own title (which describe the product type, not a feature),
  so "keeps contents cold for long periods" relates to "Double wall vacuum
  insulation keeps drinks cold for 24 hours" without exact wording.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from atlas_amazon.evidence.identity import make_evidence
from atlas_amazon.keywords.candidates import EDGE_STOPWORDS
from atlas_amazon.keywords.coverage import contains_phrase
from atlas_amazon.keywords.normalize import fold_plural, keyword_key, tokenize
from atlas_amazon.models import Evidence, EvidenceKind, ProductInput


class Polarity(StrEnum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    MIXED = "mixed"
    NEUTRAL = "neutral"


_PAYLOAD_KEYS = frozenset(
    {
        "theme",
        "polarity",
        "review_evidence_ids",
        "products",
        "count",
        "terms",
        "extractor",
        "extractor_version",
        "rationale",
    }
)


class ReviewThemeError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ReviewTheme:
    evidence_id: str
    theme: str
    polarity: Polarity
    count: int
    products: tuple[str, ...]
    review_evidence_ids: tuple[str, ...]
    terms: tuple[str, ...]
    extractor: str
    extractor_version: str
    rationale: str


def _products_of(review_ids: Sequence[str], reviews: Mapping[str, Evidence]) -> list[str]:
    products = set()
    for rid in review_ids:
        review = reviews.get(rid)
        if review is None:
            raise ReviewThemeError(f"references unknown review evidence {rid!r}")
        if review.kind != EvidenceKind.REVIEW_SAMPLE:
            raise ReviewThemeError(f"{rid!r} is not review_sample evidence")
        asin = review.payload.get("asin", review.subject)
        if not isinstance(asin, str) or not asin:
            raise ReviewThemeError(f"review {rid!r} has no ASIN")
        products.add(asin)
    return sorted(products)


def review_theme_evidence(
    *,
    provider: str,
    theme: str,
    polarity: Polarity | str,
    reviews: Sequence[Evidence],
    terms: Sequence[str],
    extractor: str,
    extractor_version: str,
    rationale: str,
    marketplace: str,
    run_id: str | None,
    extracted_at,
    source_url: str | None = None,
) -> Evidence:
    """Build theme evidence from the actual review evidence it summarizes."""
    if not theme.strip() or not reviews:
        raise ReviewThemeError("a theme needs a name and at least one supporting review")
    ids = list(dict.fromkeys(r.id for r in reviews))
    payload = {
        "theme": theme,
        "polarity": Polarity(polarity).value,
        "review_evidence_ids": ids,
        "products": _products_of(ids, {r.id: r for r in reviews}),
        "count": len(ids),
        "terms": list(terms),
        "extractor": extractor,
        "extractor_version": extractor_version,
        "rationale": rationale,
    }
    return make_evidence(
        provider=provider,
        kind=EvidenceKind.REVIEW_THEME,
        marketplace=marketplace,
        retrieved_at=extracted_at,
        payload=payload,
        subject=theme,
        run_id=run_id,
        source_url=source_url,
    )


def parse_review_theme(evidence: Evidence, reviews: Mapping[str, Evidence]) -> ReviewTheme:
    if evidence.kind != EvidenceKind.REVIEW_THEME:
        raise ReviewThemeError(f"expected review_theme evidence, got {evidence.kind!r}")
    p = evidence.payload
    if set(p) != _PAYLOAD_KEYS:
        raise ReviewThemeError(f"review_theme payload keys mismatch: {sorted(p)}")
    try:
        polarity = Polarity(p["polarity"])
    except ValueError:
        raise ReviewThemeError(f"unknown polarity {p['polarity']!r}") from None
    ids = p["review_evidence_ids"]
    if not ids or len(set(ids)) != len(ids):
        raise ReviewThemeError("review_evidence_ids must be non-empty and unique")
    if p["count"] != len(ids):
        raise ReviewThemeError(f"count {p['count']} != {len(ids)} supporting reviews")
    if list(p["products"]) != _products_of(ids, reviews):
        raise ReviewThemeError("products do not match the referenced reviews")
    for name in ("theme", "extractor", "extractor_version", "rationale"):
        if not isinstance(p[name], str) or not p[name].strip():
            raise ReviewThemeError(f"{name} must be a non-empty string")
    return ReviewTheme(
        evidence_id=evidence.id,
        theme=p["theme"],
        polarity=polarity,
        count=p["count"],
        products=tuple(p["products"]),
        review_evidence_ids=tuple(ids),
        terms=tuple(p["terms"]),
        extractor=p["extractor"],
        extractor_version=p["extractor_version"],
        rationale=p["rationale"],
    )


@dataclass(frozen=True, slots=True)
class ThemeInsight:
    theme: ReviewTheme
    competitor_products: tuple[str, ...]
    about_own_product: bool
    repeated: bool  # count >= min_count

    @property
    def evidence_ids(self) -> tuple[str, ...]:
        return (self.theme.evidence_id, *self.theme.review_evidence_ids)


@dataclass(frozen=True, slots=True)
class ListingOpportunity:
    theme: str
    basis: str  # "competitor_complaint" | "competitor_praise"
    statement: str
    first_party_support: tuple[str, ...]  # verbatim ProductInput features related to the theme
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ThemeReport:
    positives: tuple[ThemeInsight, ...]
    complaints: tuple[ThemeInsight, ...]
    other: tuple[ThemeInsight, ...]  # not repeated, or mixed/neutral
    opportunities: tuple[ListingOpportunity, ...]
    invalid: tuple[tuple[str, str], ...]  # (evidence_id, reason)
    min_count: int


def _features(product: ProductInput) -> tuple[str, ...]:
    raw = product.attributes.get("features", ())
    if isinstance(raw, str):
        return (raw,)
    return tuple(f for f in raw if isinstance(f, str) and f.strip())


MIN_SHARED_WORDS = 2
GENERIC_WORDS = frozenset(
    {
        "no",
        "not",
        "very",
        "really",
        "great",
        "good",
        "nice",
        "love",
        "all",
        "most",
        "long",
        "product",
        "item",
        "one",
        "it",
        "is",
        "are",
        "was",
        "be",
        "this",
        "that",
        "they",
    }
)


def _words(text: str, ignore: frozenset[str]) -> set[str]:
    return {
        fold_plural(t)
        for t in tokenize(text)
        if t not in EDGE_STOPWORDS and t not in GENERIC_WORDS and fold_plural(t) not in ignore
    }


def _recurring_review_words(
    theme: ReviewTheme, reviews: Mapping[str, Evidence], ignore: frozenset[str]
) -> set[str]:
    counts: dict[str, int] = {}
    for rid in theme.review_evidence_ids:
        review = reviews.get(rid)
        text = review.payload.get("text") if review is not None else None
        if isinstance(text, str):
            for word in _words(text, ignore):
                counts[word] = counts.get(word, 0) + 1
    return {w for w, n in counts.items() if n >= 2}


def _supporting_features(
    theme: ReviewTheme,
    features: Sequence[str],
    *,
    title_words: frozenset[str] = frozenset(),
    reviews: Mapping[str, Evidence] | None = None,
) -> tuple[str, ...]:
    theme_words = _words(" ".join((theme.theme, *theme.terms)), title_words)
    review_words = (
        _recurring_review_words(theme, reviews, title_words) - theme_words if reviews else set()
    )
    found = []
    for feature in features:
        folded = [fold_plural(t) for t in tokenize(feature)]
        if any(contains_phrase(folded, keyword_key(term)) for term in theme.terms):
            found.append(feature)
            continue
        feature_words = _words(feature, title_words)
        shared = feature_words & theme_words
        if len(shared) >= MIN_SHARED_WORDS or (shared and feature_words & review_words):
            found.append(feature)
    return tuple(found)


def summarize_review_themes(
    themes: Sequence[Evidence],
    reviews: Sequence[Evidence],
    *,
    product: ProductInput,
    min_count: int = 2,
) -> ThemeReport:
    if min_count < 1:
        raise ValueError("min_count must be >= 1")
    by_id = {r.id: r for r in reviews}
    insights: list[ThemeInsight] = []
    invalid: list[tuple[str, str]] = []
    for evidence in themes:
        try:
            theme = parse_review_theme(evidence, by_id)
        except ReviewThemeError as exc:
            invalid.append((evidence.id, str(exc)))
            continue
        own = product.asin in theme.products if product.asin else False
        insights.append(
            ThemeInsight(
                theme=theme,
                competitor_products=tuple(a for a in theme.products if a != product.asin),
                about_own_product=own,
                repeated=theme.count >= min_count,
            )
        )
    order = sorted(insights, key=lambda i: (-i.theme.count, i.theme.theme))
    positives = tuple(i for i in order if i.repeated and i.theme.polarity is Polarity.POSITIVE)
    complaints = tuple(i for i in order if i.repeated and i.theme.polarity is Polarity.NEGATIVE)
    other = tuple(i for i in order if i not in positives and i not in complaints)

    features = _features(product)
    title_words = frozenset(fold_plural(t) for t in tokenize(product.title))
    opportunities = []
    for insight, basis in [(i, "competitor_complaint") for i in complaints] + [
        (i, "competitor_praise") for i in positives
    ]:
        if not insight.competitor_products:
            continue  # only our own reviews: not a competitive opportunity
        t = insight.theme
        n = len(insight.competitor_products)
        if basis == "competitor_complaint":
            statement = (
                f"Buyers of {n} competitor product(s) repeatedly report '{t.theme}' "
                f"({t.count} reviews). Address it in the listing only if the product "
                f"genuinely avoids this problem."
            )
        else:
            statement = (
                f"Buyers of {n} competitor product(s) repeatedly value '{t.theme}' "
                f"({t.count} reviews). If the product offers this, make sure the listing "
                f"says so."
            )
        support = _supporting_features(t, features, title_words=title_words, reviews=by_id)
        if support:
            statement += f" ProductInput lists related feature(s): {'; '.join(support)}."
        opportunities.append(
            ListingOpportunity(t.theme, basis, statement, support, insight.evidence_ids)
        )
    return ThemeReport(
        positives, complaints, other, tuple(opportunities), tuple(invalid), min_count
    )
