"""End-to-end offline scenarios: fixture -> ResearchRun -> report."""

import json
from pathlib import Path

import pytest

from atlas_amazon.evidence import JsonlEvidenceStore
from atlas_amazon.planner.recommend import RecommendationKind
from atlas_amazon.report import render_markdown, report_dict, report_json
from atlas_amazon.research import TaskStatus, load_scenario

SCENARIOS = Path(__file__).parent / "fixtures" / "scenarios"
ALL = sorted(p.stem for p in SCENARIOS.glob("*.json"))


def scenario(name):
    return load_scenario(SCENARIOS / f"{name}.json")


@pytest.fixture(scope="module")
def results():
    return {name: scenario(name).run() for name in ALL}


def test_at_least_the_four_required_scenarios_exist():
    assert {
        "book_cozy_mystery",
        "physical_water_bottle",
        "partial_missing_data",
        "well_covered_listing",
    } <= set(ALL)


@pytest.mark.parametrize("name", ALL)
def test_scenario_invariants(results, name):
    r = results[name]
    # Ranking is sorted and every score decomposes exactly.
    scores = [s.score for s in r.ranked]
    assert scores == sorted(scores, reverse=True)
    for s in r.ranked:
        assert s.score == pytest.approx(sum(c.contribution for c in s.contributions))
        assert set(s.heuristic_signals) == {"relevance", "intent"}
        for c in s.contributions:
            if c.signal in ("demand", "competition", "competitor_coverage"):
                assert c.evidence_ids, (name, s.keyword, c.signal)
    # Unscored keywords say exactly what is missing.
    for d in r.unscored:
        assert d.missing and all(d.notes[m].startswith("missing:") for m in d.missing)
    # Every recommendation and proposal carries evidence; proposals are validated.
    assert all(rec.evidence_ids for rec in r.recommendations)
    assert all(p.evidence_ids for p in r.proposals)
    assert len(r.validations) == len(r.proposals)
    assert all(v.valid for v in r.validations)
    # Every priority produced a record.
    assert [t.priority for t in r.tasks] == list(r.metadata.research_priorities)


@pytest.mark.parametrize("name", ALL)
def test_scenarios_are_reproducible(results, name):
    again = scenario(name).run()
    assert again == results[name]
    assert report_json(again) == report_json(results[name])


class TestBookScenario:
    def test_book_run(self, results):
        r = results["book_cozy_mystery"]
        assert r.metadata.recipe_id == "book"
        statuses = {t.priority: t.status for t in r.tasks}
        assert statuses["browse_categories"] is TaskStatus.UNSUPPORTED
        assert statuses["series_and_format_signals"] is TaskStatus.UNSUPPORTED
        assert statuses["reader_review_themes"] is TaskStatus.EXECUTED
        assert r.ranked[0].keyword == "cozy mystery"
        plan = r.backend_plan
        assert plan.mode == "slots" and plan.field_name == "keywords"
        value = r.proposals[0].value
        assert isinstance(value, tuple) and 1 <= len(value) <= 7
        assert all(len(slot) <= 50 for slot in value)
        # KDP avoid-terms ("book", "kindle unlimited") never reach the keyword boxes.
        assert not any("kindle unlimited" in slot or "book" in slot.split() for slot in value)
        assert {x.rule_id for x in plan.rule_exclusions} == {"keyword_avoid_terms"}
        # "cozy mystery" is fully covered by the subtitle, so it is excluded as visible
        # (longer phrases containing it still add new words and may be packed).
        assert "cozy mystery" not in plan.packed_keywords
        assert ("cozy mystery", "in_visible_listing") in {
            (e.term, e.reason.value) for e in plan.exclusions
        }
        # Existing keyword box "harbor town" has metrics, so it is ranked, not merely retained.
        assert "harbor town" in [s.keyword for s in r.ranked]

    def test_book_recommendations(self, results):
        recs = {x.keyword: x for x in results["book_cozy_mystery"].recommendations}
        assert recs["cozy mystery"].kind is RecommendationKind.PLACEMENT_UPGRADE
        assert recs["cozy mystery"].current_fields == ("subtitle",)
        assert recs["cozy mystery"].suggested_fields == ("title",)
        assert recs["small town mystery"].kind is RecommendationKind.KEYWORD_GAP


class TestPhysicalScenario:
    def test_physical_run(self, results):
        r = results["physical_water_bottle"]
        assert r.audit.passed
        assert [f.rule_id for f in r.audit.warnings] == ["backend_repetition"]
        p = r.proposals[0]
        assert p.target_field == "search_terms"
        assert len(p.value.encode("utf-8")) <= 249
        assert p.value.split()[-3:] == ["flask", "gym", "hiking"]  # current terms retained
        assert r.backend_plan.retained == ("flask", "gym", "hiking")
        gaps = [x.keyword for x in r.recommendations if x.kind is RecommendationKind.KEYWORD_GAP]
        assert "insulated water bottle" in gaps
        assert set(r.evidence.candidates_without_metrics) == {
            "insulated water",
            "wall vacuum",
            "wall vacuum insulation",
        }


class TestPartialData:
    def test_missing_data_stays_explicit(self, results):
        r = results["partial_missing_data"]
        statuses = {t.priority: t.status for t in r.tasks}
        assert statuses["review_themes"] is TaskStatus.NO_PROVIDER
        assert "no suggestion provider" in next(
            t.note for t in r.tasks if t.priority == "search_term_demand"
        )
        assert r.evidence.competitors_without_catalog == ("B0YOGA0002",)
        assert set(r.evidence.seeds_without_suggestions) == {
            "yoga mat",
            "non slip yoga mat",
            "thick yoga mat",
        }
        assert [s.keyword for s in r.ranked] == ["yoga mat"]
        unscored = {d.keyword: d for d in r.unscored}
        assert unscored["non slip yoga mat"].missing == ("competition",)
        assert unscored["thick yoga mat"].missing == ("demand", "competition")
        # One competitor and min_support 2 -> no shared competitor phrases.
        assert all(c.sources[0].value == "seed" for c in r.candidates)


class TestWellCovered:
    def test_most_high_value_keywords_already_covered(self, results):
        r = results["well_covered_listing"]
        top = r.coverage.keywords[:5]
        assert all(k.covered for k in top)
        assert r.coverage.exact_rate >= 0.8
        assert not [x for x in r.recommendations if x.kind is RecommendationKind.KEYWORD_GAP]
        assert r.proposals == ()  # nothing new to pack: all terms already visible
        assert "no ranked keyword could be packed" in r.backend_plan.note


def test_end_to_end_smoke_with_jsonl(tmp_path):
    """Full offline run against a real JSONL store, then a fresh reopen and re-run."""
    path = tmp_path / "evidence.jsonl"
    sc = scenario("book_cozy_mystery")
    first = sc.run(store=JsonlEvidenceStore(path))
    reopened = JsonlEvidenceStore(path)
    reopened.verify()
    assert len(reopened) == first.evidence.total
    second = sc.run(store=reopened)
    assert len(reopened) == first.evidence.total  # nothing duplicated
    a, b = report_dict(first), report_dict(second)
    # Only the new/reused bookkeeping differs; every derived result is identical.
    assert [t["new_records"] for t in b["tasks"]] == [0] * len(b["tasks"])
    assert [t["reused_records"] for t in b["tasks"]] == [t["new_records"] for t in a["tasks"]]
    a.pop("tasks"), b.pop("tasks")
    assert a == b

    markdown = render_markdown(first)
    for heading in (
        "# Research report",
        "## Research tasks",
        "## Evidence summary",
        "## Current listing audit",
        "## Ranked keywords",
        "## Signal breakdown",
        "## Recommendations",
        "## Proposals",
    ):
        assert heading in markdown
    assert "VALID" in markdown
    json.loads(report_json(first))  # well-formed JSON
    (tmp_path / "report.md").write_text(markdown, encoding="utf-8")
