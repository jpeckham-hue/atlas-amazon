import pytest

from atlas_amazon.backend import (
    ExclusionReason,
    backend_byte_length,
    pack_backend_bytes,
    pack_keyword_slots,
)


def reasons(result):
    return {(e.term, e.reason) for e in result.excluded}


class TestByteLength:
    def test_ascii_and_multibyte(self):
        assert backend_byte_length("abc def") == 7
        assert backend_byte_length("café") == 5  # é is 2 bytes in UTF-8
        assert backend_byte_length("日本") == 6

    def test_spaces_optional(self):
        assert backend_byte_length("a b c", count_spaces=False) == 3


class TestPackBackendBytes:
    def test_dedupes_folds_plurals_and_drops_stopwords(self):
        result = pack_backend_bytes(
            ["water bottle for kids", "Water Bottles", "kid"],
            max_bytes=250,
            stopwords=["for"],
        )
        assert result.included == ("water", "bottle", "kids")
        assert ("for", ExclusionReason.STOPWORD) in reasons(result)
        assert ("bottles", ExclusionReason.DUPLICATE) in reasons(result)
        assert ("kid", ExclusionReason.DUPLICATE) in reasons(result)

    def test_excludes_words_visible_in_listing(self):
        result = pack_backend_bytes(
            ["insulated tumbler", "travel mug"], max_bytes=250, visible=["Insulated Travel Mug"]
        )
        assert result.included == ("tumbler",)
        assert ("insulated", ExclusionReason.IN_VISIBLE_LISTING) in reasons(result)

    def test_respects_byte_budget_and_keeps_filling_with_smaller_words(self):
        result = pack_backend_bytes(["aaaa", "bbbbbbbbbb", "cc"], max_bytes=8)
        # "aaaa" (4) + " bbbbbbbbbb" would be 15 > 8, skip; + " cc" = 7 fits
        assert result.text == "aaaa cc"
        assert result.byte_count == 7
        assert result.remaining_bytes == 1
        assert ("bbbbbbbbbb", ExclusionReason.OVER_BUDGET) in reasons(result)

    def test_multibyte_counts_bytes_not_chars(self):
        result = pack_backend_bytes(["café", "tea"], max_bytes=8)
        # "café" = 5 bytes; "café tea" = 9 bytes > 8
        assert result.included == ("café",)

    def test_never_exceeds_budget(self):
        words = [f"word{i}" for i in range(200)]
        result = pack_backend_bytes(words, max_bytes=250)
        assert result.byte_count <= 250
        assert len(result.text.encode("utf-8")) == result.byte_count

    def test_count_spaces_false_packs_more(self):
        words = ["aaaa", "bbbb", "cccc"]
        with_spaces = pack_backend_bytes(words, max_bytes=12)
        without = pack_backend_bytes(words, max_bytes=12, count_spaces=False)
        assert len(without.included) > len(with_spaces.included)

    def test_empty_candidate_is_reported(self):
        result = pack_backend_bytes(["!!!", "ok"], max_bytes=10)
        assert ("!!!", ExclusionReason.EMPTY) in reasons(result)
        assert result.included == ("ok",)

    def test_rejects_non_positive_budget(self):
        with pytest.raises(ValueError):
            pack_backend_bytes(["x"], max_bytes=0)

    def test_every_candidate_token_is_accounted_for(self):
        candidates = ["the best water bottle", "bottle", "x" * 300, ""]
        result = pack_backend_bytes(candidates, max_bytes=20, stopwords=["the"])
        total = sum(max(len(c.split()), 1) for c in candidates)
        assert len(result.included) + len(result.excluded) == total


class TestPackKeywordSlots:
    def test_first_fit_into_slots(self):
        result = pack_keyword_slots(["aaaa", "bbbb", "cccc"], slots=2, slot_max_chars=9)
        assert result.slots == ("aaaa bbbb", "cccc")
        assert result.placed == (("aaaa", 0), ("bbbb", 0), ("cccc", 1))

    def test_too_long_duplicate_and_over_budget(self):
        result = pack_keyword_slots(
            ["cozy mystery", "Cozy Mysteries", "x" * 51, "small town romance", "detective"],
            slots=1,
            slot_max_chars=50,
        )
        assert result.slots == ("cozy mystery small town romance detective",)
        assert ("cozy mysteries", ExclusionReason.DUPLICATE) in reasons(result)
        assert ("x" * 51, ExclusionReason.TOO_LONG) in reasons(result)

        full = pack_keyword_slots(["aaaaa", "bbbbb"], slots=1, slot_max_chars=5)
        assert ("bbbbb", ExclusionReason.OVER_BUDGET) in reasons(full)

    def test_phrases_fully_in_visible_text_are_dropped(self):
        result = pack_keyword_slots(
            ["dragon fantasy", "epic dragon fantasy"],
            slots=7,
            slot_max_chars=50,
            visible=["Dragon Fantasy: The Saga"],
        )
        assert result.slots[0] == "epic dragon fantasy"
        assert ("dragon fantasy", ExclusionReason.IN_VISIBLE_LISTING) in reasons(result)

    def test_slot_lengths_never_exceed_limit(self):
        phrases = [f"phrase number {i}" for i in range(40)]
        result = pack_keyword_slots(phrases, slots=7, slot_max_chars=50)
        assert len(result.slots) == 7
        assert all(len(s) <= 50 for s in result.slots)
        assert len(result.placed) + len(result.excluded) == 40

    def test_rejects_non_positive_shapes(self):
        with pytest.raises(ValueError):
            pack_keyword_slots(["x"], slots=0, slot_max_chars=50)
