import pytest

from atlas_amazon.keywords import compute_coverage, contains_phrase
from atlas_amazon.models import Listing

WEIGHTS = {"title": 1.0, "bullets": 0.5, "search_terms": 0.25}


def test_contains_phrase():
    hay = ["insulated", "water", "bottle", "for", "kids"]
    assert contains_phrase(hay, ["water", "bottle"])
    assert not contains_phrase(hay, ["bottle", "water"])
    assert not contains_phrase(hay, ["water", "kids"])
    assert not contains_phrase(hay, [])
    assert not contains_phrase([], ["water"])


def test_placement_uses_best_field_relative_to_max_weight():
    listing = Listing(
        {
            "title": "Insulated Water Bottle",
            "bullets": ["Keeps drinks cold", "Leak proof lid"],
            "search_terms": "gym hiking",
        }
    )
    report = compute_coverage(
        ["water bottles", "leak proof", "hiking", "coffee mug"], listing, WEIGHTS
    )
    by_kw = {k.keyword: k for k in report.keywords}

    assert by_kw["water bottles"].best_field == "title"
    assert by_kw["water bottles"].placement_score == 1.0
    assert by_kw["leak proof"].best_field == "bullets"
    assert by_kw["leak proof"].placement_score == 0.5
    assert by_kw["hiking"].placement_score == 0.25
    assert by_kw["coffee mug"].placement_score == 0.0
    assert by_kw["coffee mug"].best_field is None

    assert report.exact_rate == pytest.approx(3 / 4)
    assert report.placement_score == pytest.approx((1.0 + 0.5 + 0.25 + 0.0) / 4)
    assert report.uncovered == ("coffee mug",)


def test_phrases_do_not_span_bullet_boundaries():
    listing = Listing({"title": "x", "bullets": ["made of steel", "water bottle"]})
    report = compute_coverage(["steel water"], listing, WEIGHTS)
    kc = report.keywords[0]
    assert not kc.covered
    assert kc.token_fraction == 1.0  # both words present, just not adjacent


def test_token_fraction_counts_unique_tokens_across_fields():
    listing = Listing({"title": "Running Shoes", "search_terms": "trail"})
    kc = compute_coverage(["trail running jacket"], listing, WEIGHTS).keywords[0]
    assert kc.token_fraction == pytest.approx(2 / 3)


def test_unweighted_fields_are_ignored():
    listing = Listing({"title": "Mug", "description": "ceramic coffee mug"})
    kc = compute_coverage(["coffee"], listing, WEIGHTS).keywords[0]
    assert not kc.covered
    assert kc.token_fraction == 0.0


def test_keywords_are_deduplicated():
    listing = Listing({"title": "Water Bottle"})
    report = compute_coverage(["water bottle", "Water Bottles"], listing, WEIGHTS)
    assert len(report.keywords) == 1


def test_empty_keyword_list_yields_zero_rates():
    report = compute_coverage([], Listing({"title": "x"}), WEIGHTS)
    assert report.exact_rate == report.token_rate == report.placement_score == 0.0


@pytest.mark.parametrize("weights", [{}, {"title": 0.0}, {"title": -1.0}])
def test_invalid_weights(weights):
    with pytest.raises(ValueError):
        compute_coverage(["x"], Listing({"title": "x"}), weights)
