import pytest

from atlas_amazon.keywords.scoring import KeywordSignals, SignalValue, rank_keywords
from atlas_amazon.models import Listing
from atlas_amazon.planner.recommend import (
    RecommendationKind,
    keyword_recommendations,
    plan_backend,
)
from atlas_amazon.recipes import load_recipe
from conftest import T0


@pytest.fixture(scope="module")
def product():
    return load_recipe("physical-product")


@pytest.fixture(scope="module")
def book():
    return load_recipe("book")


def ranked(recipe, *keywords):
    """Rank keywords so the given order is preserved (descending relevance)."""
    n = len(keywords)
    items = []
    for i, kw in enumerate(keywords):
        sv = SignalValue(0.5, (f"ev_{i}",))
        items.append(KeywordSignals(kw, SignalValue(1 - i / (n + 1)), sv, sv, SignalValue(0.5), sv))
    return rank_keywords(items, recipe.keyword_weights)


class TestBackendBytes:
    def test_packs_best_first_with_lineage(self, product):
        listing = Listing({"title": "Acme Water Bottle"})
        scores = ranked(product, "insulated water bottle", "kids bottle", "gym flask")
        plan = plan_backend(product, listing, scores, created_at=T0)
        assert plan.proposal.value == "insulated kids gym flask"
        assert plan.proposal.target_field == "search_terms"
        assert plan.packed_keywords == ("insulated water bottle", "kids bottle", "gym flask")
        assert plan.proposal.evidence_ids == ("ev_0", "ev_1", "ev_2")
        assert plan.used == len("insulated kids gym flask") and plan.capacity == 249
        assert "in_visible_listing" in plan.proposal.rationale

    def test_prohibited_terms_removed_before_packing(self, product):
        scores = ranked(product, "best bottle", "cheap flask")
        plan = plan_backend(product, Listing({"title": "Mug"}), scores, created_at=T0)
        assert [(r.keyword, r.rule_id) for r in plan.rule_exclusions] == [
            ("best bottle", "backend_prohibited_terms")
        ]
        assert plan.proposal.value == "cheap flask"
        assert plan.proposal.evidence_ids == ("ev_1",)

    def test_current_terms_are_retained_not_dropped(self, product):
        listing = Listing({"title": "Mug", "search_terms": "camping camping travel"})
        plan = plan_backend(product, listing, ranked(product, "coffee cup"), created_at=T0)
        assert plan.proposal.value == "coffee cup camping travel"
        assert plan.retained == ("camping", "travel")
        assert "Retains current unscored content: camping, travel" in plan.proposal.rationale
        assert plan.proposal.evidence_ids == ("ev_0",)  # retained terms add no evidence

    def test_no_proposal_when_unchanged(self, product):
        listing = Listing({"title": "Mug", "search_terms": "coffee cup"})
        plan = plan_backend(product, listing, ranked(product, "coffee cup"), created_at=T0)
        assert plan.proposal is None
        assert "already equals" in plan.note

    def test_no_proposal_without_ranked_keywords(self, product):
        plan = plan_backend(product, Listing({"title": "Mug"}), [], created_at=T0)
        assert plan.proposal is None and plan.note == "no ranked keywords to pack"

    def test_no_proposal_when_everything_is_visible(self, product):
        plan = plan_backend(
            product, Listing({"title": "Coffee Cup"}), ranked(product, "coffee cup"), created_at=T0
        )
        assert plan.proposal is None
        assert "no ranked keyword could be packed" in plan.note

    def test_recipe_without_backend(self):
        base = load_recipe("amazon-base")
        assert plan_backend(base, Listing({"title": "x"}), [], created_at=T0) is None


class TestBackendSlots:
    def test_slots_respect_visible_and_avoid_terms(self, book):
        listing = Listing({"title": "The Quiet Harbor", "subtitle": "A Cozy Mystery"})
        scores = ranked(
            book, "cozy mystery", "small town mystery", "mystery books", "amateur sleuth"
        )
        plan = plan_backend(book, listing, scores, created_at=T0)
        assert plan.mode == "slots"
        assert plan.proposal.value == ("small town mystery amateur sleuth",)
        assert [r.rule_id for r in plan.rule_exclusions] == ["keyword_avoid_terms"]
        assert {e.reason.value for e in plan.exclusions} == {"in_visible_listing"}
        assert plan.used == 1 and plan.capacity == 7


class TestKeywordRecommendations:
    def test_gaps_and_placement_upgrades(self, product):
        listing = Listing(
            {
                "title": "Acme Water Bottle",
                "bullets": ["Leak proof lid"],
                "search_terms": "gym",
            }
        )
        scores = ranked(product, "water bottle", "leak proof", "gym", "straw lid")
        coverage, recs = keyword_recommendations(product, listing, scores, top_n=10)
        kinds = {r.keyword: r.kind for r in recs}
        assert "water bottle" not in kinds  # already in the title
        assert kinds["leak proof"] is RecommendationKind.PLACEMENT_UPGRADE
        assert kinds["gym"] is RecommendationKind.PLACEMENT_UPGRADE  # backend only
        assert kinds["straw lid"] is RecommendationKind.KEYWORD_GAP
        upgrade = next(r for r in recs if r.keyword == "leak proof")
        assert upgrade.current_fields == ("bullets",)
        assert upgrade.suggested_fields == ("title", "item_highlights")
        gap = next(r for r in recs if r.keyword == "straw lid")
        assert gap.suggested_fields == ("title", "item_highlights", "bullets", "description")
        assert gap.rank == 4
        assert gap.evidence_ids == scores[3].evidence_ids
        assert gap.heuristic_signals == ("relevance", "intent")
        assert coverage.exact_rate == pytest.approx(3 / 4)

    def test_top_n_limits_recommendations(self, product):
        scores = ranked(product, "a b", "c d", "e f")
        _, recs = keyword_recommendations(product, Listing({"title": "x"}), scores, top_n=2)
        assert [r.rank for r in recs] == [1, 2]
        with pytest.raises(ValueError):
            keyword_recommendations(product, Listing({"title": "x"}), scores, top_n=0)

    def test_blocked_fields_cite_rules(self, product):
        scores = ranked(product, "hot item mug")
        _, [rec] = keyword_recommendations(product, Listing({"title": "x"}), scores, top_n=5)
        assert ("title", "title_subjective_commentary") in rec.blocked_fields
        assert "title" not in rec.suggested_fields

    def test_covered_by_proposal_link(self, product):
        listing = Listing({"title": "Mug"})
        scores = ranked(product, "travel cup")
        plan = plan_backend(product, listing, scores, created_at=T0)
        _, [rec] = keyword_recommendations(product, listing, scores, top_n=5, backend_plan=plan)
        assert rec.covered_by_proposal == plan.proposal.id

    def test_no_ranked_keywords(self, product):
        assert keyword_recommendations(product, Listing({"title": "x"}), [], top_n=5) == (None, [])
