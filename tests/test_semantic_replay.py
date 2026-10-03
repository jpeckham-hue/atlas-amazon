"""End-to-end replay of recorded semantic runs, human overrides and evaluation.

The recordings in tests/fixtures/recordings/ are SYNTHETIC: produced by the
live code path against `fixture_responder` (scripted, not a model), so CI can
exercise recording -> replay -> evaluation offline. Regenerate with:

    ATLAS_REGEN_RECORDINGS=1 pytest tests/test_semantic_replay.py
"""

import json
import os

import pytest

from atlas_amazon.providers import FixtureData
from atlas_amazon.report import render_markdown, report_dict, report_json
from atlas_amazon.research import load_scenario
from atlas_amazon.semantic import (
    LLMJudgmentProvider,
    LLMReviewThemeProvider,
    RecordingTransport,
    ReplayTransport,
    ScriptedTransport,
    SemanticBudget,
    UsageLedger,
    evaluate_judgments,
    render_evaluation_markdown,
)
from atlas_amazon.semantic.synthetic import SYNTHETIC_MODEL, fixture_responder
from atlas_amazon.semantic.usage import estimate_recording_cost
from semantic_helpers import RECORDINGS, SCENARIOS

DEVIATIONS = {
    "book_cozy_mystery": {
        ("relevance", "small town"): {
            "score": 0.65,
            "confidence": 0.7,
            "rationale": "A small-town setting is a core cozy-mystery convention.",
        },
        ("intent", "cozy mystery"): {
            "label": "transactional",
            "score": 0.8,
            "confidence": 0.6,
            "rationale": "Genre queries on Amazon usually precede a purchase.",
        },
    },
    "physical_water_bottle": {
        ("relevance", "straw lid"): {
            "score": 0.5,
            "confidence": 0.6,
            "rationale": "Straw lids are a common accessory in this category.",
        },
        ("intent", "water bottle"): {
            "label": "transactional",
            "score": 0.75,
            "confidence": 0.6,
            "rationale": "Most shoppers searching this phrase buy within the session.",
        },
    },
}
NAMES = sorted(DEVIATIONS)


def regenerate(name):
    raw = json.loads((SCENARIOS / f"{name}.json").read_text(encoding="utf-8"))
    fixture = FixtureData.from_dict(raw["fixture"], origin=f"{name}.json")
    path = RECORDINGS / f"{name}.jsonl"
    if path.exists():
        path.unlink()
    responder = fixture_responder(fixture, deviations=DEVIATIONS[name])
    ledger = UsageLedger()
    transport = RecordingTransport(ScriptedTransport(responder), path)
    load_scenario(SCENARIOS / f"{name}.json").with_providers(
        judgments=LLMJudgmentProvider(transport, ledger=ledger),
        review_themes=LLMReviewThemeProvider(transport, ledger=ledger),
    ).run()


def replay_scenario(name, ledger=None):
    path = RECORDINGS / f"{name}.jsonl"
    ledger = ledger or UsageLedger()
    transport = ReplayTransport(path)
    return (
        load_scenario(SCENARIOS / f"{name}.json")
        .with_providers(
            judgments=LLMJudgmentProvider(transport, ledger=ledger),
            review_themes=LLMReviewThemeProvider(transport, ledger=ledger),
        )
        .run()
    )


@pytest.fixture(scope="module", autouse=True)
def recordings():
    if os.environ.get("ATLAS_REGEN_RECORDINGS") == "1":
        for name in NAMES:
            regenerate(name)
    for name in NAMES:
        assert (RECORDINGS / f"{name}.jsonl").exists(), f"missing recording for {name}"


@pytest.mark.parametrize("name", NAMES)
def test_replay_is_reproducible_and_offline(name):
    first, second = replay_scenario(name), replay_scenario(name)
    assert report_json(first) == report_json(second)
    usage = first.semantic_usage
    assert usage.live_calls == 0
    [group] = usage.groups
    assert group.model == SYNTHETIC_MODEL and group.replayed == group.requests
    assert "replay_miss" not in group.failures  # every request was recorded


@pytest.mark.parametrize("name", NAMES)
def test_replayed_judgments_carry_call_lineage(name):
    result = replay_scenario(name)
    model_judgments = [j for j in result.judgments if not j.is_human]
    assert model_judgments
    for j in model_judgments:
        assert j.model == SYNTHETIC_MODEL and j.provider == "anthropic"
        assert j.call["synthetic"] is True
        assert j.call["call_evidence_id"] in result.evidence.ids_by_kind["semantic_call"]
    themes = result.review_themes
    assert themes is not None and themes.complaints  # LLM themes summarized deterministically


def test_human_override_beats_replayed_model_judgment():
    result = replay_scenario("book_cozy_mystery")
    [series] = [
        r
        for r in result.judgment_resolutions
        if r.subject == "cozy mystery series" and r.type.value == "relevance"
    ]
    assert series.overridden and series.used.is_human
    assert series.model.model == SYNTHETIC_MODEL
    assert {series.model.evidence_id, series.human.evidence_id} <= set(
        result.evidence.ids_by_kind["judgment"]
    )  # both records preserved
    d = result.derivation("cozy mystery series")
    assert d.sources["relevance"].value == "human"
    assert series.human.evidence_id in d.signals.relevance.evidence_ids
    md = render_markdown(result)
    assert "### Human overrides" in md and "human:editor" in md
    row = next(
        k for k in report_dict(result)["ranked_keywords"] if k["keyword"] == "cozy mystery series"
    )
    assert {s["signal"]: s["source"] for s in row["signals"]}["relevance"] == "human"


@pytest.mark.parametrize("name", NAMES)
def test_evaluation_reports_each_type_separately(name):
    reference = load_scenario(SCENARIOS / f"{name}.json").run()
    candidate = replay_scenario(name)
    report = evaluate_judgments(
        candidate.judgments,
        reference.judgments,
        candidate_label="replayed model",
        reference_label="fixture",
    )
    assert [t.type.value for t in report.by_type] == [
        "relevance",
        "intent",
        "entity",
        "equivalence",
    ]
    deviated = {(kind, subject) for kind, subject in DEVIATIONS[name]}
    for t in report.by_type:
        found = {(t.type.value, d.subject) for d in t.disagreements}
        assert found == {k for k in deviated if k[0] == t.type.value}
        for d in t.disagreements:
            assert d.reference_rationale and d.candidate_rationale
    md = render_evaluation_markdown(report)
    assert "no combined score" in md and "## relevance disagreements" in md


def test_evaluation_metrics():
    report = evaluate_judgments(
        replay_scenario("physical_water_bottle").judgments,
        load_scenario(SCENARIOS / "physical_water_bottle.json").run().judgments,
    )
    rel, intent, entity, eq = report.by_type
    assert rel.agreed == rel.compared - 1 and "mean_absolute_error" in rel.extra
    assert intent.agreed == intent.compared - 1
    assert entity.agreement_rate == 1.0 and entity.extra["blocking_agreement_rate"] == 1.0
    assert eq.agreement_rate == 1.0
    assert rel.candidate_only  # the model answered keywords the fixture had no reference for


def test_call_limit_during_a_full_run_degrades_to_heuristics():
    from atlas_amazon.semantic.synthetic import fixture_responder as responder

    raw = json.loads((SCENARIOS / "physical_water_bottle.json").read_text(encoding="utf-8"))
    fixture = FixtureData.from_dict(raw["fixture"])
    ledger = UsageLedger(budget=SemanticBudget(max_live_calls=5))
    transport = ScriptedTransport(responder(fixture))
    result = (
        load_scenario(SCENARIOS / "physical_water_bottle.json")
        .with_providers(
            judgments=LLMJudgmentProvider(transport, ledger=ledger),
            review_themes=LLMReviewThemeProvider(transport, ledger=ledger),
        )
        .run()
    )
    assert len(transport.requests) == 5
    assert result.semantic_usage.live_calls == 5
    assert result.semantic_usage.halts
    sources = {d.sources["relevance"].value for d in result.derivations}
    assert sources == {"judgment", "heuristic"}  # explicit fallback, still ranked
    assert "Limit reached" in render_markdown(result)


@pytest.mark.parametrize("name", NAMES)
def test_recordings_are_marked_synthetic_and_secret_free(name):
    from atlas_amazon.semantic import find_secrets
    from atlas_amazon.semantic.records import ChecksummedJsonl

    records = ChecksummedJsonl(RECORDINGS / f"{name}.jsonl").read()
    assert records and all(r["response"]["synthetic"] for r in records)
    assert not find_secrets(records)
    estimate = estimate_recording_cost(RECORDINGS / f"{name}.jsonl", "claude-opus-5-5")
    assert estimate.calls == len(records) and estimate.estimated_cost_usd > 0
    assert estimate.worst_case_cost_usd >= estimate.estimated_cost_usd
