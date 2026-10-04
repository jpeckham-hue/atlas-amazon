"""v0.9 closing pass: format-word intent rule and the feature-support gate, offline.

The live v0.9 answers (tests/fixtures/recordings/live/v09/) are served to the
current pipeline: the deterministic rules run first (so the new format-word
intent rule pre-empts "cozy mystery books"), the recorded model answers fill
in the rest, and the support gate keeps unsupported feature keywords out of
recommendations and backend terms. No live calls; sockets are blocked.

Generated report (must stay current):

    ATLAS_REGEN_EXAMPLES=1 pytest tests/test_v09_closing.py
"""

import socket

import pytest

from atlas_amazon.jsonvalue import thaw
from atlas_amazon.judgments import JudgmentRequest, JudgmentType
from atlas_amazon.planner.support import feature_support
from atlas_amazon.recipes import load_recipe
from atlas_amazon.research import ResearchConfig, load_scenario
from atlas_amazon.semantic import (
    LLMReviewThemeProvider,
    ReplayTransport,
    evaluate_judgments,
)
from atlas_amazon.semantic.recorded import final_judgments, recorded_judgments
from atlas_amazon.semantic.review import human_judgments, load_review_decisions, supersede
from atlas_amazon.semantic.strategies import PrecomputedJudgmentProvider
from semantic_helpers import HISTORICAL, RECORDINGS, SCENARIOS
from test_examples import ROOT, check
from test_live_v09 import replay as replay_v09
from test_v08_calibration import REVIEWS
from test_v09_intent import context

V09 = RECORDINGS / "live" / "v09"
NAMES = ["book_cozy_mystery", "physical_water_bottle"]
TYPES = ("relevance", "intent", "entity", "equivalence")


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise OSError("network access is disabled")

    monkeypatch.setattr(socket, "socket", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


def closing(name, config=None):
    """The v0.9 live answers served to the current pipeline."""
    sc = load_scenario(SCENARIOS / f"{name}.json")
    recorded = recorded_judgments(
        V09 / f"{name}.jsonl", prompt_version="judgment_batch-v3", run_id=sc.run_id
    )
    final = {j.evidence_id for j in final_judgments(recorded)}
    served = [r.evidence for r in recorded if r.evidence.id in final]
    themes = LLMReviewThemeProvider(ReplayTransport(V09 / f"{name}.jsonl"))
    return sc.with_providers(
        judgments=PrecomputedJudgmentProvider(served), review_themes=themes
    ).run(config=config)


def reference(name, judgments):
    fixture = load_scenario(SCENARIOS / f"{name}.json").run(config=HISTORICAL)
    provider = load_review_decisions(REVIEWS / "v08_human_decisions.json")[name]
    requests = [JudgmentRequest(j.type, j.input) for j in judgments]
    return supersede(fixture.judgments, human_judgments(provider, requests))


def agreement(name, result):
    report = evaluate_judgments(
        result.judgments, reference(name, result.judgments), reference_humans=True
    )
    return report, {t.type.value: (t.agreed, t.compared) for t in report.by_type}


@pytest.fixture(scope="module")
def runs():
    return {name: (replay_v09(name), closing(name)) for name in NAMES}


def judged(result, kind, subject):
    return next(j for j in result.judgments if j.type.value == kind and j.subject == subject)


# -- 1. format-word intent ---------------------------------------------------------


class TestFormatWordIntent:
    def test_format_word_shopping_is_transactional(self, runs):
        _, after = runs["book_cozy_mystery"]
        j = judged(after, "intent", "cozy mystery books")
        assert (j.label, j.provider, j.model) == (
            "transactional",
            "rules",
            "rules:format_word_shopping",
        )
        assert judged(after, "intent", "small town mystery books").label == "transactional"

    def test_bare_genre_browsing_stays_with_the_model(self, runs):
        _, after = runs["book_cozy_mystery"]
        j = judged(after, "intent", "small town mystery")
        assert (j.label, j.score, j.provider) == ("commercial_investigation", 0.7, "anthropic")
        # A bare genre with a format word is a broad category: not the rule's business.
        assert judged(after, "intent", "mystery books").provider == "anthropic"

    def test_bottle_water_stays_transactional(self, runs):
        _, after = runs["physical_water_bottle"]
        j = judged(after, "intent", "bottle water")
        assert (j.label, j.score) == ("transactional", 0.8)

    def test_rule_can_be_turned_off(self):
        legacy = closing("book_cozy_mystery", ResearchConfig(intent_rules=False))
        assert judged(legacy, "intent", "cozy mystery books").provider == "anthropic"


# -- 2. feature-support gate -------------------------------------------------------------


class TestFeatureSupport:
    def test_unsupported_feature_keywords_are_blocked(self, runs):
        before, after = runs["physical_water_bottle"]
        assert "bpa free" in {r.keyword for r in before.recommendations}  # the v0.9 problem
        blocked = {
            "bpa free",
            "straw lid",
            "water bottle with straw",
            "water bottles for kids",
            "insulated water bottle with straw",
        }
        assert not blocked & {r.keyword for r in after.recommendations}
        assert not blocked & set(after.backend_plan.packed_keywords)
        proposal = " ".join(str(p.value) for p in after.proposals)
        assert "bpa" not in proposal.split() and "straw" not in proposal.split()
        assert all(v.valid for v in after.validations)

    def test_supported_feature_keywords_are_still_allowed(self, runs):
        _, after = runs["physical_water_bottle"]
        allowed = {r.keyword for r in after.recommendations}
        assert {"double wall vacuum", "leak proof", "vacuum insulation"} <= allowed

    def test_unsupported_opportunities_stay_visible_and_flagged(self, runs):
        _, after = runs["physical_water_bottle"]
        flagged = {u.keyword: u for u in after.unsupported_opportunities}
        assert {"bpa free", "straw lid", "water bottles for kids"} <= set(flagged)
        bpa = flagged["bpa free"]
        assert bpa.rule_id == "unsupported_by_product"
        assert bpa.unsupported_terms == ("bpa", "free")
        assert set(bpa.checked_sources) >= {"product_title", "features", "description"}
        ranked = {s.keyword for s in after.ranked}
        assert set(flagged) <= ranked  # still researched and ranked, not discarded

    def test_evidence_lineage_survives_the_support_check(self, runs):
        _, after = runs["physical_water_bottle"]
        stored = {e for ids in after.evidence.ids_by_kind.values() for e in ids}
        for opportunity in after.unsupported_opportunities:
            assert opportunity.evidence_ids and set(opportunity.evidence_ids) <= stored
            metrics = set(after.evidence.ids_by_kind["keyword_metric"])
            assert set(opportunity.evidence_ids) & metrics  # the market side of the story
        exclusions = {x.keyword: x for x in after.backend_plan.rule_exclusions}
        assert exclusions["bpa free"].rule_id == "unsupported_by_product"
        assert exclusions["bpa free"].terms == ("bpa", "free")

    def test_book_claims_mode_only_checks_attribute_claims(self):
        mode = load_recipe("book").claims_mode
        ctx = context("book_cozy_mystery")
        assert not feature_support("cozy mystery with cats", ctx, mode).supported
        for keyword in ("small town", "amateur sleuth", "harbor town", "mystery books"):
            assert feature_support(keyword, ctx, mode).supported


# -- 3. evaluation -------------------------------------------------------------------


def test_semantic_agreement_after_the_closing_pass(runs):
    _, book = agreement("book_cozy_mystery", runs["book_cozy_mystery"][1])
    _, bottle = agreement("physical_water_bottle", runs["physical_water_bottle"][1])
    assert book == {
        "relevance": (10, 11),
        "intent": (4, 4),
        "entity": (3, 3),
        "equivalence": (1, 1),
    }
    assert bottle == {
        "relevance": (12, 12),
        "intent": (5, 5),
        "entity": (6, 6),
        "equivalence": (2, 2),
    }


def test_structure_is_unchanged(runs):
    for before, after in runs.values():
        assert [f.phrases for f in after.families.families] == [
            f.phrases for f in before.families.families
        ]
        assert {f.keyword for f in after.entity_flags} == {f.keyword for f in before.entity_flags}


# -- report ---------------------------------------------------------------------------


def _fmt(j):
    r = thaw(j.result)
    return f"{r['label']} {r['score']:g}" if j.type is JudgmentType.INTENT else f"{r['score']:g}"


def render(runs) -> str:
    out = [
        "# v0.9 closing pass (offline)",
        "",
        "> **No live calls.** The v0.9 live answers (`tests/fixtures/recordings/live/v09/`) "
        "are served to the current pipeline: deterministic rules first (including the new "
        "format-word intent rule), recorded model answers for the rest, then the new "
        "feature-support gate on recommendations and backend terms.",
        "",
        "## Agreement with the human-reviewed reference",
        "",
        "| Scenario | Version | relevance | intent | entity | equivalence |",
        "|---|---|---|---|---|---|",
    ]
    for name, (before, after) in runs.items():
        for label, result in (("v0.9 live", before), ("v0.9 closing pass", after)):
            _, row = agreement(name, result)
            out.append(
                f"| {name} | {label} | "
                + " | ".join(f"{row[k][0]}/{row[k][1]}" for k in TYPES)
                + " |"
            )
    out += [
        "",
        "## Target judgments",
        "",
        "| Keyword | v0.9 live | Closing pass | Source |",
        "|---|---|---|---|",
    ]
    for name, kind, subject in (
        ("book_cozy_mystery", "intent", "cozy mystery books"),
        ("book_cozy_mystery", "intent", "small town mystery books"),
        ("book_cozy_mystery", "intent", "small town mystery"),
        ("physical_water_bottle", "intent", "bottle water"),
    ):
        before, after = runs[name]
        a, b = judged(before, kind, subject), judged(after, kind, subject)
        out.append(f"| {subject} ({kind}) | {_fmt(a)} | {_fmt(b)} | {b.model} |")
    out += ["", "## Unsupported feature keywords", ""]
    for name, (before, after) in runs.items():
        out += [f"### {name}", ""]
        if not after.unsupported_opportunities:
            out += ["None.", ""]
            continue
        out += [
            "| Keyword | Rank | Unsupported terms | Recommended in v0.9 live | "
            "Packed in v0.9 live |",
            "|---|---|---|---|---|",
        ]
        before_recs = {r.keyword for r in before.recommendations}
        before_packed = set(before.backend_plan.packed_keywords) if before.backend_plan else set()
        for u in after.unsupported_opportunities:
            out.append(
                f"| {u.keyword} | {u.rank} | {', '.join(u.unsupported_terms)} | "
                f"{'yes' if u.keyword in before_recs else 'no'} | "
                f"{'yes' if u.keyword in before_packed else 'no'} |"
            )
        out.append("")
    out += ["## Downstream: v0.9 live vs closing pass", ""]
    for name, (before, after) in runs.items():
        out += [
            f"### {name}",
            "",
            f"- Recommendations: v0.9 live {[r.keyword for r in before.recommendations]}; "
            f"closing pass {[r.keyword for r in after.recommendations]}.",
            f"- Backend proposal: v0.9 live `{[str(p.value) for p in before.proposals]}`; "
            f"closing pass `{[str(p.value) for p in after.proposals]}`; passes audit: "
            f"{all(v.valid for v in after.validations)}.",
            f"- Keyword families and entity blocking: unchanged "
            f"({sorted((f.keyword, f.label) for f in after.entity_flags)}).",
            "",
        ]
    return "\n".join(out)


def test_closing_report_is_current(runs):
    check(ROOT / "docs" / "baselines" / "live_v0.9_closing.md", render(runs))
