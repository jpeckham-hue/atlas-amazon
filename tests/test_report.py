"""The report layer only formats: every value must trace back to the ResearchResult."""

import json
from pathlib import Path

import pytest

from atlas_amazon.report import render_markdown, report_dict, report_json
from atlas_amazon.research import load_scenario

SCENARIOS = Path(__file__).parent / "fixtures" / "scenarios"


@pytest.fixture(scope="module", params=sorted(p.stem for p in SCENARIOS.glob("*.json")))
def result(request):
    return load_scenario(SCENARIOS / f"{request.param}.json").run()


def test_dict_mirrors_result_exactly(result):
    d = report_dict(result)
    assert d["run"]["run_id"] == result.metadata.run_id
    assert d["run"]["evidence_fingerprint"] == result.metadata.evidence_fingerprint
    assert [k["keyword"] for k in d["ranked_keywords"]] == [s.keyword for s in result.ranked]
    for row, score in zip(d["ranked_keywords"], result.ranked, strict=True):
        assert row["score"] == score.score
        assert row["evidence_ids"] == list(score.evidence_ids)
        for cell, c in zip(row["signals"], score.contributions, strict=True):
            assert (cell["signal"], cell["weight"], cell["contribution"]) == (
                c.signal,
                c.weight,
                c.contribution,
            )
            assert cell["evidence_ids"] == list(c.evidence_ids)
            assert cell["derivation"] == result.derivation(score.keyword).notes[c.signal]
    assert [r["keyword"] for r in d["recommendations"]] == [
        r.keyword for r in result.recommendations
    ]
    assert [p["id"] for p in d["proposals"]] == [p.id for p in result.proposals]
    assert len(d["audit"]["findings"]) == len(result.audit.findings)
    assert d["evidence"]["total"] == result.evidence.total


def test_every_derived_recommendation_lists_evidence(result):
    d = report_dict(result)
    for row in d["ranked_keywords"]:
        assert row["evidence_ids"]
    for rec in d["recommendations"]:
        assert rec["evidence_ids"]
    for proposal in d["proposals"]:
        assert proposal["evidence_ids"]
        assert "validation" in proposal
    for item in d["unscored_keywords"]:
        assert item["missing_signals"]


def test_json_is_valid_and_stable(result):
    text = report_json(result)
    assert json.loads(text) == json.loads(json.dumps(report_dict(result)))
    assert report_json(result) == text


def test_markdown_shows_every_ranked_keyword_and_proposal(result):
    md = render_markdown(result)
    for score in result.ranked:
        assert f"| {score.keyword}" in md
    for proposal in result.proposals:
        assert proposal.id in md
    for d in result.unscored:
        assert f"- {d.keyword}:" in md
    assert md.endswith("\n") and "\r" not in md
