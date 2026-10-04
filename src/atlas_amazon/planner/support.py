"""First-party support for feature claims in recommended keywords (v0.9 closing pass).

A keyword like "bpa free" or "straw lid" claims something about the product.
Atlas must not recommend it for listing copy or backend terms unless the
seller's own product information says so. Such keywords are not dropped:
they stay ranked and are reported as market opportunities marked
`unsupported_by_product`, with the market evidence and the missing support.

**Evidence** is the seller's first-party text only: product title, subtitle,
brand, author, features and listing description (see
`judgments.context.product_context`). Seed keywords are targets, not facts,
and are never evidence.

**Claimed words** depend on the recipe's `[support] claims` mode:

* `descriptors` (physical products): every content word that is not part of
  the product type (the title's words, the seeds' head nouns and the
  category) describes the product, so it must be supported ("bpa", "free",
  "straw", "kids").
* `attributes` (books, the default): genre, topic and setting words are
  relevance questions, not claims; only unit words, compound attributes
  ("x free", "x proof", "x resistant", "x safe") and the words of a
  "with/without/for ..." phrase are claims ("cozy mystery with cats").

A keyword is supported when every claimed word appears in the evidence.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from atlas_amazon.keywords.candidates import EDGE_STOPWORDS
from atlas_amazon.keywords.families import COMPOUND_ATTRIBUTE_HEADS, UNIT_WORDS
from atlas_amazon.keywords.normalize import fold_plural, tokenize

UNSUPPORTED_RULE = "unsupported_by_product"
CLAIM_MODES = ("attributes", "descriptors")
EVIDENCE_FIELDS = ("product_title", "subtitle", "brand", "author", "features", "description")
CLAIM_CONNECTORS = frozenset({"with", "without", "for"})


@dataclass(frozen=True, slots=True)
class UnsupportedOpportunity:
    """A ranked keyword with market evidence whose feature claim the product lacks.

    Kept visible as a market opportunity, never recommended for copy or backend.
    """

    keyword: str  # family canonical
    rank: int  # 1-based position in the ranking
    score: float
    unsupported_terms: tuple[str, ...]  # claimed words with no first-party support
    claimed_terms: tuple[str, ...]
    checked_sources: tuple[str, ...]  # first-party fields that were searched
    evidence_ids: tuple[str, ...]  # market evidence behind the keyword (metrics, catalog, ...)
    rule_id: str = "unsupported_by_product"


@dataclass(frozen=True, slots=True)
class FeatureSupport:
    keyword: str
    mode: str
    claimed: tuple[str, ...]  # words the keyword claims about the product
    unsupported: tuple[str, ...]  # claimed words absent from first-party evidence
    supporting_text: tuple[str, ...]  # first-party texts that contain claimed words

    @property
    def supported(self) -> bool:
        return not self.unsupported


def _fold(text: str) -> set[str]:
    return {fold_plural(t) for t in tokenize(text) if t not in EDGE_STOPWORDS}


def evidence_texts(context: Mapping[str, Any]) -> list[str]:
    texts: list[str] = []
    for key in EVIDENCE_FIELDS:
        value = context.get(key)
        if isinstance(value, list | tuple):
            texts += [str(v) for v in value if str(v).strip()]
        elif value:
            texts.append(str(value))
    return texts


def _head(seed: str) -> str | None:
    words = [fold_plural(t) for t in tokenize(seed) if t not in EDGE_STOPWORDS]
    return words[-1] if words else None


def claimed_words(keyword: str, context: Mapping[str, Any], mode: str) -> list[str]:
    tokens = tokenize(keyword)
    if mode == "descriptors":
        product_type = _fold(str(context.get("product_title", "")))
        product_type |= _fold(str(context.get("category", "")).replace("-", " "))
        product_type |= {h for h in (_head(str(s)) for s in context.get("seeds", ())) if h}
        return [
            fold_plural(t)
            for t in tokens
            if t not in EDGE_STOPWORDS and fold_plural(t) not in product_type
        ]
    claimed: list[str] = []
    after_connector = False
    for i, token in enumerate(tokens):
        if token in CLAIM_CONNECTORS:
            after_connector = True
            continue
        if token in EDGE_STOPWORDS:
            continue
        compound = token in COMPOUND_ATTRIBUTE_HEADS or (
            i + 1 < len(tokens) and tokens[i + 1] in COMPOUND_ATTRIBUTE_HEADS
        )
        if after_connector or compound or token in UNIT_WORDS:
            claimed.append(fold_plural(token))
    return claimed


def feature_support(keyword: str, context: Mapping[str, Any], mode: str) -> FeatureSupport:
    if mode not in CLAIM_MODES:
        raise ValueError(f"unknown claims mode {mode!r}")
    claimed = list(dict.fromkeys(claimed_words(keyword, context, mode)))
    texts = evidence_texts(context)
    evidence = set().union(*(_fold(t) for t in texts)) if texts else set()
    unsupported = tuple(w for w in claimed if w not in evidence)
    supporting = tuple(t for t in texts if _fold(t) & set(claimed))
    return FeatureSupport(keyword, mode, tuple(claimed), unsupported, supporting)
