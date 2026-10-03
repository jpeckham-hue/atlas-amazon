import math

import pytest

from atlas_amazon.evidence import make_evidence
from atlas_amazon.keywords.candidates import build_candidates
from atlas_amazon.keywords.families import singleton_families
from atlas_amazon.keywords.signals import (
    derive_signals,
    heuristic_intent,
    heuristic_relevance,
    reference_terms_for,
)
from conftest import T0


def metric(keyword, **payload):
    return make_evidence(
        provider="t",
        kind="keyword_metric",
        marketplace="US",
        retrieved_at=T0,
        payload={"keyword": keyword, **payload},
        subject=keyword,
        run_id="r",
    )


def catalog(asin, title):
    return make_evidence(
        provider="t",
        kind="catalog_item",
        marketplace="US",
        retrieved_at=T0,
        payload={"title": title},
        subject=asin,
        run_id="r",
    )


COMPETITORS = [
    catalog("B0C0000001", "Insulated Water Bottle"),
    catalog("B0C0000002", "Steel Flask"),
]


def derive(seeds, metrics, competitors=COMPETITORS, refs=("water bottle",)):
    candidates = build_candidates(seeds=seeds, suggestions=[], competitors=[])
    return {
        d.keyword: d
        for d in derive_signals(
            singleton_families(candidates),
            metrics=metrics,
            competitors=competitors,
            reference_terms=refs,
        )
    }


class TestEvidenceSignals:
    def test_full_derivation_with_lineage(self):
        m1 = metric("water bottle", search_volume=1000, competition=0.8)
        m2 = metric("insulated water bottle", search_volume=100, competition=0.3)
        d = derive(["water bottle", "insulated water bottle"], [m1, m2])
        top = d["water bottle"]
        assert top.scorable and top.missing == ()
        s = top.signals
        assert s.demand.value == pytest.approx(1.0)
        assert s.demand.evidence_ids == (m1.id,)
        assert s.competition.value == 0.8 and s.competition.evidence_ids == (m1.id,)
        assert s.competitor_coverage.value == 0.5
        assert s.competitor_coverage.evidence_ids == tuple(c.id for c in COMPETITORS)
        low = d["insulated water bottle"].signals
        assert low.demand.value == pytest.approx(math.log1p(100) / math.log1p(1000))
        assert "log1p(100) / log1p(1000)" in d["insulated water bottle"].notes["demand"]
        assert "1/2 competitor listings" in d["insulated water bottle"].notes["competitor_coverage"]

    def test_missing_metric_is_explicit_not_defaulted(self):
        d = derive(
            ["water bottle", "flask"], [metric("water bottle", search_volume=5, competition=0.5)]
        )
        flask = d["flask"]
        assert not flask.scorable
        assert flask.signals is None
        assert flask.missing == ("demand", "competition")
        assert flask.notes["demand"] == "missing: no keyword_metric evidence"

    @pytest.mark.parametrize(
        ("payload", "missing"),
        [
            ({"search_volume": -1, "competition": 0.5}, ("demand",)),
            ({"search_volume": "lots", "competition": 0.5}, ("demand",)),
            ({"search_volume": 10}, ("competition",)),
            ({"search_volume": 10, "competition": 1.5}, ("competition",)),
            ({"search_volume": True, "competition": 0.5}, ("demand",)),
        ],
    )
    def test_invalid_metric_values_count_as_missing(self, payload, missing):
        d = derive(["mug"], [metric("mug", **payload)])
        assert d["mug"].missing == missing
        assert d["mug"].notes[missing[0]].startswith("missing:")

    def test_no_competitors_means_coverage_missing(self):
        d = derive(["mug"], [metric("mug", search_volume=1, competition=0.1)], competitors=[])
        assert d["mug"].missing == ("competitor_coverage",)

    def test_zero_volume_ceiling(self):
        d = derive(["mug"], [metric("mug", search_volume=0, competition=0.1)])
        assert d["mug"].signals.demand.value == 0.0
        assert d["mug"].signals.demand.evidence_ids  # still evidence-backed

    def test_duplicate_metrics_first_wins_and_is_noted(self):
        first = metric("mug", search_volume=10, competition=0.1)
        second = make_evidence(
            provider="other",
            kind="keyword_metric",
            marketplace="US",
            retrieved_at=T0,
            payload={"keyword": "mugs", "search_volume": 99, "competition": 0.9},
            run_id="r",
        )
        d = derive(["mug"], [first, second])
        assert d["mug"].signals.competition.evidence_ids == (first.id,)
        assert second.id in d["mug"].notes["demand"]

    def test_ceiling_uses_only_candidate_metrics(self):
        stray = metric("unrelated giant", search_volume=10**9, competition=0.5)
        d = derive(["mug"], [metric("mug", search_volume=100, competition=0.1), stray])
        assert d["mug"].signals.demand.value == pytest.approx(1.0)

    def test_wrong_kind_rejected(self):
        with pytest.raises(ValueError):
            derive(["mug"], [COMPETITORS[0]])


class TestHeuristics:
    def test_relevance_is_heuristic_and_explained(self):
        d = derive(["water bottle"], [metric("water bottle", search_volume=1, competition=0)])
        s = d["water bottle"].signals
        assert s.relevance.evidence_ids == () and s.intent.evidence_ids == ()
        assert d["water bottle"].notes["relevance"].startswith("heuristic:")
        assert d["water bottle"].notes["intent"].startswith("heuristic:")

    def test_relevance_formula(self):
        value, note = heuristic_relevance("water bottles for kids", ["insulated water bottle"])
        assert value == pytest.approx(2 / 3)  # "for" ignored; water, bottle hit; kids misses
        assert "2/3" in note
        assert heuristic_relevance("for the", ["x"])[0] == 0.0

    @pytest.mark.parametrize(
        ("keyword", "value"), [("mug", 0.25), ("a b c", 0.75), ("a b c d e", 1.0)]
    )
    def test_intent_formula(self, keyword, value):
        assert heuristic_intent(keyword)[0] == value

    def test_reference_terms(self):
        assert reference_terms_for("The Quiet Harbor!", ["Cozy Mystery", " "]) == (
            "the quiet harbor",
            "cozy mystery",
        )
