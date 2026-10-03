import pytest

from atlas_amazon.evidence import make_evidence
from atlas_amazon.keywords.candidates import (
    CandidateSource,
    build_candidates,
    competitor_listing,
    shared_competitor_phrases,
)
from conftest import T0


def catalog(asin, **payload):
    return make_evidence(
        provider="t",
        kind="catalog_item",
        marketplace="US",
        retrieved_at=T0,
        payload=payload,
        subject=asin,
        run_id="r",
    )


def suggestion(seed, items):
    return make_evidence(
        provider="t",
        kind="autocomplete_suggestion",
        marketplace="US",
        retrieved_at=T0,
        payload={"seed": seed, "suggestions": items},
        subject=seed,
        run_id="r",
    )


C1 = catalog("B0C0000001", title="Insulated Water Bottle with Straw", bullets=["Leak proof lid"])
C2 = catalog("B0C0000002", title="Steel Water Bottle, Insulated", bullets=["Leak proof cap"])
C3 = catalog("B0C0000003", title="Coffee Mug for the Office", brand="Mugs")


class TestCompetitorListing:
    def test_reads_text_fields_only(self):
        ev = catalog(
            "B0C0000009",
            title="T",
            bullets=["a", "b"],
            brand="X",
            price=9.99,
            description=["not", 1],
        )
        listing = competitor_listing(ev)
        assert dict(listing.fields) == {"title": "T", "bullets": ("a", "b")}

    def test_rejects_other_kinds(self):
        with pytest.raises(ValueError):
            competitor_listing(suggestion("x", []))


class TestSharedPhrases:
    def test_support_threshold_and_lineage(self):
        phrases = dict(shared_competitor_phrases([C1, C2, C3], min_support=2))
        assert phrases["water bottle"] == (C1.id, C2.id)
        assert phrases["leak proof"] == (C1.id, C2.id)
        assert "coffee mug" not in phrases  # only one competitor
        assert all(len(ids) >= 2 for ids in phrases.values())

    def test_edge_stopwords_and_digits_excluded(self):
        a = catalog("B0C0000004", title="Bottle for the Gym 32 oz, 2024 2025 model")
        b = catalog("B0C0000005", title="Bottle for the Gym 32 oz, 2024 2025 model")
        phrases = {p for p, _ in shared_competitor_phrases([a, b], min_support=2)}
        assert "bottle for" not in phrases and "for the" not in phrases
        assert "the gym" not in phrases
        assert "2024 2025" not in phrases  # digits only
        assert "32 oz" in phrases  # digits plus a word are allowed
        assert "gym 32 oz" in phrases
        assert all(len(p.split()) <= 3 for p in phrases)

    def test_one_count_per_competitor(self):
        a = catalog("B0C0000006", title="water bottle water bottle", bullets=["water bottle"])
        phrases = dict(shared_competitor_phrases([a], min_support=1))
        assert phrases["water bottle"] == (a.id,)

    def test_min_support_validation(self):
        with pytest.raises(ValueError):
            shared_competitor_phrases([C1], min_support=0)


class TestBuildCandidates:
    def test_merges_sources_and_evidence(self):
        s = suggestion("water bottle", ["Water Bottles With Straw", "water bottle"])
        candidates = build_candidates(
            seeds=["Water Bottle"],
            suggestions=[s],
            competitors=[C1, C2, C3],
            listing_phrases=["leak proof"],
        )
        by_kw = {c.keyword: c for c in candidates}
        wb = by_kw["water bottle"]
        assert wb.sources == (
            CandidateSource.SEED,
            CandidateSource.SUGGESTION,
            CandidateSource.COMPETITOR,
        )
        assert wb.evidence_ids == (s.id, C1.id, C2.id)
        assert by_kw["water bottles with straw"].sources == (CandidateSource.SUGGESTION,)
        assert by_kw["leak proof"].sources == (CandidateSource.LISTING, CandidateSource.COMPETITOR)
        assert candidates[0].keyword == "water bottle"  # seeds first

    def test_plural_variants_merge_to_first_spelling(self):
        candidates = build_candidates(
            seeds=["water bottles"],
            suggestions=[suggestion("w", ["water bottle"])],
            competitors=[],
        )
        assert [c.keyword for c in candidates] == ["water bottles"]

    def test_seeds_and_listing_carry_no_evidence(self):
        candidates = build_candidates(
            seeds=["mug"], suggestions=[], competitors=[], listing_phrases=["tea cup"]
        )
        assert all(c.evidence_ids == () for c in candidates)

    def test_empty_and_wrong_kind(self):
        assert build_candidates(seeds=["!!!"], suggestions=[], competitors=[]) == []
        with pytest.raises(ValueError):
            build_candidates(seeds=[], suggestions=[C1], competitors=[])

    def test_deterministic(self):
        args = dict(
            seeds=["water bottle"], suggestions=[suggestion("w", ["x y"])], competitors=[C1, C2]
        )
        assert build_candidates(**args) == build_candidates(**args)
