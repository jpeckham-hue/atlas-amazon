import itertools
import math

import pytest

from atlas_amazon.keywords.scoring import (
    KeywordSignals,
    SignalValue,
    competitor_coverage_signal,
    linear_signal,
    log_scaled_signal,
    rank_keywords,
    score_keyword,
    validate_weights,
)
from atlas_amazon.models import Listing
from atlas_amazon.recipes import KEYWORD_SIGNALS, load_recipe

WEIGHTS = {
    "relevance": 0.35,
    "demand": 0.25,
    "competition": 0.15,
    "intent": 0.15,
    "competitor_coverage": 0.10,
}


def signals(keyword="water bottle", rel=0.9, dem=0.8, comp=0.6, intent=0.7, cov=0.5, ids=True):
    def sv(value, name):
        return SignalValue(value, (f"ev_{name}_{keyword}",) if ids else ())

    return KeywordSignals(
        keyword=keyword,
        relevance=sv(rel, "rel"),
        demand=sv(dem, "dem"),
        competition=sv(comp, "comp"),
        intent=sv(intent, "int"),
        competitor_coverage=sv(cov, "cov"),
    )


class TestScoreKeyword:
    def test_formula_and_decomposition(self):
        result = score_keyword(signals(), WEIGHTS)
        expected = 0.35 * 0.9 + 0.25 * 0.8 + 0.15 * (1 - 0.6) + 0.15 * 0.7 + 0.10 * 0.5
        assert result.score == pytest.approx(expected)
        assert [c.signal for c in result.contributions] == list(KEYWORD_SIGNALS)
        assert result.score == math.fsum(c.contribution for c in result.contributions)
        for c in result.contributions:
            assert c.contribution == pytest.approx(c.weight * c.normalized_value)
        assert result.weights == WEIGHTS

    def test_competition_is_inverted_and_marked(self):
        comp = score_keyword(signals(comp=0.6), WEIGHTS).contribution("competition")
        assert comp.inverted
        assert comp.raw_value == 0.6
        assert comp.normalized_value == pytest.approx(0.4)
        rel = score_keyword(signals(), WEIGHTS).contribution("relevance")
        assert not rel.inverted and rel.normalized_value == rel.raw_value

    def test_more_competition_lowers_the_score(self):
        easy = score_keyword(signals(comp=0.1), WEIGHTS).score
        hard = score_keyword(signals(comp=0.9), WEIGHTS).score
        assert easy > hard

    def test_evidence_ids_are_retained_per_signal(self):
        result = score_keyword(signals(), WEIGHTS)
        assert result.contribution("demand").evidence_ids == ("ev_dem_water bottle",)
        assert len(result.evidence_ids) == 5
        assert result.heuristic_signals == ()

    def test_signals_without_evidence_are_flagged_heuristic(self):
        result = score_keyword(signals(ids=False), WEIGHTS)
        assert result.heuristic_signals == tuple(KEYWORD_SIGNALS)
        assert all(c.heuristic for c in result.contributions)

    def test_shared_evidence_is_deduplicated_in_summary(self):
        shared = SignalValue(0.5, ("ev_metric",))
        s = KeywordSignals("mug", shared, shared, shared, SignalValue(0.5), SignalValue(0.5))
        result = score_keyword(s, WEIGHTS)
        assert result.evidence_ids == ("ev_metric",)
        assert result.heuristic_signals == ("intent", "competitor_coverage")

    def test_score_is_bounded_in_unit_interval(self):
        for values in itertools.product((0.0, 0.5, 1.0), repeat=5):
            s = score_keyword(signals(*("k",), *values), WEIGHTS).score
            assert 0.0 <= s <= 1.0 + 1e-12
        best = score_keyword(signals(rel=1, dem=1, comp=0, intent=1, cov=1), WEIGHTS)
        assert best.score == pytest.approx(1.0)

    @pytest.mark.parametrize("rid", ["amazon-base", "book", "physical-product"])
    def test_recipe_weights_are_accepted(self, rid):
        recipe = load_recipe(rid)
        result = score_keyword(signals(), recipe.keyword_weights)
        assert result.weights == dict(recipe.keyword_weights)


class TestValidation:
    @pytest.mark.parametrize(
        "weights",
        [
            {**WEIGHTS, "relevance": 0.5},  # sums to 1.15
            {k: v for k, v in WEIGHTS.items() if k != "intent"},
            {**WEIGHTS, "extra": 0.0},
            {**WEIGHTS, "relevance": -0.1, "demand": 0.7},
            {**WEIGHTS, "relevance": math.nan},
        ],
    )
    def test_invalid_weights(self, weights):
        with pytest.raises(ValueError):
            validate_weights(weights)

    def test_weight_type(self):
        with pytest.raises(TypeError):
            validate_weights({**WEIGHTS, "relevance": True})

    @pytest.mark.parametrize("value", [-0.01, 1.01, math.nan, math.inf])
    def test_signal_range(self, value):
        with pytest.raises(ValueError):
            SignalValue(value)

    def test_signal_types_and_ids(self):
        with pytest.raises(TypeError):
            SignalValue(True)  # type: ignore[arg-type]
        with pytest.raises(ValueError):
            SignalValue(0.5, ("",))
        with pytest.raises(ValueError):
            SignalValue(0.5, ("ev_a", "ev_a"))
        assert SignalValue(1, ["ev_a"]).evidence_ids == ("ev_a",)

    def test_keyword_must_have_words(self):
        with pytest.raises(ValueError):
            signals(keyword="!!!")


class TestRanking:
    def test_sorted_by_score_descending(self):
        ranked = rank_keywords(
            [signals("low", rel=0.1), signals("high", rel=1.0), signals("mid", rel=0.5)], WEIGHTS
        )
        assert [r.keyword for r in ranked] == ["high", "mid", "low"]

    def test_ties_break_deterministically(self):
        ranked = rank_keywords([signals("zebra mug"), signals("apple mug")], WEIGHTS)
        assert [r.keyword for r in ranked] == ["apple mug", "zebra mug"]
        again = rank_keywords([signals("apple mug"), signals("zebra mug")], WEIGHTS)
        assert [r.keyword for r in again] == ["apple mug", "zebra mug"]

    def test_singular_plural_duplicates_rejected(self):
        with pytest.raises(ValueError, match="duplicates"):
            rank_keywords([signals("water bottle"), signals("Water Bottles")], WEIGHTS)


class TestTransforms:
    def test_log_scaled(self):
        assert log_scaled_signal(0, 1000).value == 0.0
        assert log_scaled_signal(1000, 1000).value == pytest.approx(1.0)
        assert log_scaled_signal(5000, 1000).value == 1.0  # clamped
        mid = log_scaled_signal(31, 1023, ["ev_x"])
        assert mid.value == pytest.approx(math.log1p(31) / math.log1p(1023))
        assert mid.evidence_ids == ("ev_x",)
        with pytest.raises(ValueError):
            log_scaled_signal(-1, 10)
        with pytest.raises(ValueError):
            log_scaled_signal(1, 0)

    def test_linear(self):
        assert linear_signal(5, 0, 10).value == 0.5
        assert linear_signal(-5, 0, 10).value == 0.0
        assert linear_signal(50, 0, 10).value == 1.0
        with pytest.raises(ValueError):
            linear_signal(1, 5, 5)

    def test_competitor_coverage(self):
        competitors = [
            ("ev_c1", Listing({"title": "Insulated Water Bottle"})),
            ("ev_c2", Listing({"title": "Steel Flask", "bullets": ["Best water bottles"]})),
            ("ev_c3", Listing({"title": "Coffee Mug"})),
            ("ev_c4", Listing({"title": "Water", "bullets": ["Bottle"]})),  # split: no match
        ]
        result = competitor_coverage_signal("water bottle", competitors)
        assert result.value == pytest.approx(2 / 4)
        assert result.evidence_ids == ("ev_c1", "ev_c2", "ev_c3", "ev_c4")
        with pytest.raises(ValueError):
            competitor_coverage_signal("x", [])
