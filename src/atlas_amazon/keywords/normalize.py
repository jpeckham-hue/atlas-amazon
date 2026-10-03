"""Text normalization for keyword matching.

Two layers:

* `normalize_text` / `tokenize` are lossless enough to display: NFKC,
  casefold, apostrophes removed ("women's" -> "womens"), every other
  non-word character becomes a space.
* `fold_plural` / `keyword_key` are for *matching only* and are never shown
  to users. Folding is a small, predictable English heuristic, not a stemmer:
  it only needs to map singular and plural to the same key.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable

_APOSTROPHES = "'\u2019\u02bc`\u00b4"
_NON_WORD = re.compile(r"[\W_]+")

# Words that look plural but aren't, or whose singular differs.
_FOLD_EXCEPTIONS = frozenset(
    {"series", "species", "news", "lens", "physics", "mathematics", "always", "perhaps"}
)
_ES_PLURAL_ENDINGS = ("sses", "shes", "ches", "xes", "zes")
_NON_PLURAL_S_ENDINGS = ("ss", "us", "is")
_VOWELS = frozenset("aeiou")


def normalize_text(text: str) -> str:
    folded = unicodedata.normalize("NFKC", text).casefold()
    for ch in _APOSTROPHES:
        folded = folded.replace(ch, "")
    return " ".join(_NON_WORD.sub(" ", folded).split())


def tokenize(text: str) -> list[str]:
    return normalize_text(text).split()


def fold_plural(token: str) -> str:
    """Map a normalized token to a matching key shared by its singular/plural forms.

    The "ie" ending is the shared form for -y/-ies words, so "baby" and
    "babies" both fold to "babie", and "cookie" and "cookies" to "cookie".
    """
    if len(token) <= 3 or not token.isalpha() or token in _FOLD_EXCEPTIONS:
        return token
    if token.endswith("ies"):
        return token[:-1]
    if token.endswith("y") and token[-2] not in _VOWELS:
        return token[:-1] + "ie"
    if token.endswith(_ES_PLURAL_ENDINGS):
        return token[:-2]
    if token.endswith(_NON_PLURAL_S_ENDINGS):
        return token
    if token.endswith("s"):
        return token[:-1]
    return token


def keyword_key(phrase: str) -> tuple[str, ...]:
    """Order-preserving matching key for a phrase."""
    return tuple(fold_plural(t) for t in tokenize(phrase))


def dedupe_keywords(phrases: Iterable[str]) -> list[str]:
    """Drop empty phrases and later phrases with the same key; keep the first spelling."""
    seen: set[tuple[str, ...]] = set()
    result: list[str] = []
    for phrase in phrases:
        key = keyword_key(phrase)
        if key and key not in seen:
            seen.add(key)
            result.append(phrase)
    return result
