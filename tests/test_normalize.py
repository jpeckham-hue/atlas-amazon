import pytest

from atlas_amazon.keywords import (
    dedupe_keywords,
    fold_plural,
    keyword_key,
    normalize_text,
    tokenize,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("  Stainless-Steel   Water Bottle!! ", "stainless steel water bottle"),
        ("Women's Running Shoes", "womens running shoes"),
        ("Women\u2019s", "womens"),
        ("\uff26\uff35\uff2c\uff2c", "full"),  # fullwidth "FULL" -> NFKC
        ("STRASSE Straße", "strasse strasse"),  # casefold, not lower
        ("snake_case/and,commas", "snake case and commas"),
        ("Café 12oz", "café 12oz"),
        ("", ""),
        ("!!!", ""),
    ],
)
def test_normalize_text(raw, expected):
    assert normalize_text(raw) == expected


def test_tokenize():
    assert tokenize("Kids' Books, Ages 3-5") == ["kids", "books", "ages", "3", "5"]


@pytest.mark.parametrize(
    ("singular", "plural"),
    [
        ("book", "books"),
        ("box", "boxes"),
        ("dish", "dishes"),
        ("watch", "watches"),
        ("dress", "dresses"),
        ("baby", "babies"),
        ("cookie", "cookies"),
        ("shoe", "shoes"),
        ("story", "stories"),
    ],
)
def test_fold_plural_maps_singular_and_plural_together(singular, plural):
    assert fold_plural(singular) == fold_plural(plural)


@pytest.mark.parametrize(
    "word", ["glass", "bus", "analysis", "series", "news", "toy", "day", "cat", "12oz", "3"]
)
def test_fold_plural_leaves_non_plurals_stable(word):
    # These must not be truncated, or must be at least stable under refolding.
    assert fold_plural(fold_plural(word)) == fold_plural(word)
    assert fold_plural(word) in (word, word + "ie")


def test_fold_plural_specific_non_plurals_untouched():
    for word in ["glass", "bus", "analysis", "series", "news", "toy", "cat"]:
        assert fold_plural(word) == word


def test_keyword_key_is_order_preserving():
    assert keyword_key("Water Bottles") == ("water", "bottle")
    assert keyword_key("bottle water") != keyword_key("water bottle")


def test_dedupe_keywords_keeps_first_spelling():
    phrases = ["Water Bottle", "water bottles", "", "  ", "bottle water", "WATER-BOTTLE"]
    assert dedupe_keywords(phrases) == ["Water Bottle", "bottle water"]
