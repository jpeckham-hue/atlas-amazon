"""v0.9: intent calibration (intent vs relevance, intent-risk escalation, routing comparison).

All offline. Routing strategies are simulated from answers recorded live in
v0.7 (prompt judgment_batch-v2): fast-tier answers from the production
recordings, strong-tier answers from the strong comparison and production
escalations. The v0.9 prompt (judgment_batch-v3) cannot be measured from
those recordings; the report says so. Generated report (must stay current):

    ATLAS_REGEN_EXAMPLES=1 pytest tests/test_v09_intent.py
"""

import json
import socket

import pytest

from atlas_amazon.jsonvalue import thaw
from atlas_amazon.judgments import JudgmentRequest, JudgmentType
from atlas_amazon.judgments.context import product_context
from atlas_amazon.recipes import load_recipe
from atlas_amazon.research import load_scenario
from atlas_amazon.semantic import (
    BatchedJudgmentProvider,
    EscalationPolicy,
    LLMReviewThemeProvider,
    ReplayTransport,
    SemanticCache,
    evaluate_judgments,
)
from atlas_amazon.semantic.escalation import intent_risks
from atlas_amazon.semantic.prompts import load_template
from atlas_amazon.semantic.review import human_judgments, load_review_decisions, supersede
from atlas_amazon.semantic.strategies import (
    PrecomputedJudgmentProvider,
    simulate_strategy,
    strategy_cost,
)
from atlas_amazon.semantic.tiers import FAST, STRONG
from semantic_helpers import SCENARIOS
from test_examples import ROOT, check
from test_semantic_batch import batch_transport, judge
from test_v08_calibration import REVIEWS, V07, V08_POLICY, _scenario_data

NAMES = ["book_cozy_mystery", "physical_water_bottle"]
TYPES = ("relevance", "intent", "entity", "equivalence")


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise OSError("network access is disabled")

    monkeypatch.setattr(socket, "socket", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


def context(name):
    sc = load_scenario(SCENARIOS / f"{name}.json")
    seeds = sc.product.attributes["seed_keywords"]
    return product_context(sc.product, sc.listing, load_recipe(sc.product.recipe_id), seeds)


def intent(keyword, name):
    return JudgmentRequest.about_keyword(JudgmentType.INTENT, keyword, context=context(name))


def flagged(keyword, label, name):
    return [r.value for r, _ in intent_risks(keyword, label, context(name))]


# -- prompt contract -------------------------------------------------------------


class TestIntentPrompt:
    def test_intent_is_separated_from_relevance(self):
        batch = load_template("judgment_batch")
        assert batch.version == "judgment_batch-v3"
        assert "Intent is judged without regard to this product" in batch.user
        assert '"bottle water" is a\nshopper buying bottled water (transactional)' in batch.user
        assert (
            '"small town\nmystery"' in batch.user
            and "commercial_investigation unless" in batch.user
        )
        single = load_template("intent")
        assert single.version == "intent-v4" and "bottle water" in single.user

    def test_previous_prompt_is_kept_for_replay(self):
        old = load_template("judgment_batch", "judgment_batch-v2")
        assert old.fingerprint != load_template("judgment_batch").fingerprint
        assert "Intent is judged without regard" not in old.user

    def test_prompt_bump_invalidates_cached_answers(self, tmp_path):
        cache = SemanticCache(tmp_path / "cache.jsonl")
        requests = [intent("bottle water", "physical_water_bottle")]
        judge(
            BatchedJudgmentProvider(
                batch_transport(), cache=cache, prompt_version="judgment_batch-v2"
            ),
            requests,
        )
        old = BatchedJudgmentProvider(
            batch_transport(), cache=cache, prompt_version="judgment_batch-v2"
        )
        assert old.plan(requests).cache_hits == 1
        new = BatchedJudgmentProvider(batch_transport(), cache=cache)
        plan = new.plan(requests)
        assert (plan.cache_hits, plan.live) == (0, 1)  # same input, new prompt version: miss


# -- intent-risk signals -----------------------------------------------------------


class TestIntentRisk:
    def test_transactional_but_irrelevant_query(self):
        risks = flagged("bottle water", "informational", "physical_water_bottle")
        assert risks == ["reordered_product_phrase", "informational_without_question"]
        assert flagged("bottle water", "transactional", "physical_water_bottle") == []

    def test_genre_and_subgenre_browsing(self):
        assert flagged("small town mystery", "transactional", "book_cozy_mystery") == [
            "genre_browse"
        ]
        assert flagged("small town mystery", "commercial_investigation", "book_cozy_mystery") == []
        # A format word as head ("books") is a shopping query, as the human review decided.
        assert flagged("cozy mystery books", "transactional", "book_cozy_mystery") == []

    def test_generic_and_comparison_shopping(self):
        assert flagged("water bottles", "transactional", "physical_water_bottle") == [
            "generic_plural"
        ]
        assert flagged("best insulated water bottle", "transactional", "physical_water_bottle") == [
            "comparison_shopping"
        ]
        for keyword in ("water bottle 32 oz", "insulated water bottle"):
            assert flagged(keyword, "transactional", "physical_water_bottle") == []
        assert (
            flagged("how to clean a water bottle", "informational", "physical_water_bottle") == []
        )

    def test_risk_triggers_a_second_opinion_not_an_overwrite(self):
        def answer(request, kind, subject):
            if request["model"] == FAST.model:
                return {
                    "label": "informational",
                    "score": 0.1,
                    "confidence": 0.95,
                    "rationale": "the drink, not a container",
                }
            return {
                "label": "transactional",
                "score": 0.8,
                "confidence": 0.8,
                "rationale": "buying bottled water",
            }

        transport = batch_transport(answer)
        p = BatchedJudgmentProvider(transport)
        _, judgments = judge(p, [intent("bottle water", "physical_water_bottle")])
        [j] = judgments
        assert j.label == "transactional" and j.model == STRONG.model  # the strong answer
        assert j.call["escalation"]["reason"] == "reordered_product_phrase"
        assert j.call["escalation"]["from_result"] == {"label": "informational", "score": 0.1}

        def strong_agrees(request, kind, subject):  # a second opinion may confirm the label
            return {"label": "informational", "score": 0.2, "confidence": 0.9, "rationale": "x"}

        _, judgments = judge(
            BatchedJudgmentProvider(batch_transport(strong_agrees)),
            [intent("bottle water", "physical_water_bottle")],
        )
        assert judgments[0].label == "informational"  # never rewritten by the rule

    def test_intent_risks_can_be_disabled(self):
        policy = EscalationPolicy(intent_risks=False)
        assert (
            policy.reason(
                intent("small town mystery", "book_cozy_mystery"),
                status="ok",
                structured={"label": "transactional", "score": 0.8, "confidence": 0.9},
            )
            is None
        )


# -- offline routing comparison -------------------------------------------------------


def _human_reference(name, fixture, judgments):
    providers = load_review_decisions(REVIEWS / "v08_human_decisions.json")
    requests = [JudgmentRequest(j.type, j.input) for j in judgments]
    return supersede(fixture.judgments, human_judgments(providers[name], requests))


STRATEGIES = {
    "v0.8 routing": dict(policy=V08_POLICY),
    "intent-risk escalation (v0.9)": dict(policy=EscalationPolicy()),
    "strong tier for all intent": dict(policy=V08_POLICY, strong_types={JudgmentType.INTENT}),
}


@pytest.fixture(scope="module")
def data():
    out = {}
    for name in NAMES:
        d = _scenario_data(name)
        sc = d["scenario"]
        strategies, results = {}, {}
        for label, kwargs in STRATEGIES.items():
            outcome = simulate_strategy(label, d["fast"], d["strong_pool"], **kwargs)
            strategies[label] = outcome
            served = [d["evidence"][j.evidence_id] for j in outcome.judgments]
            themes = LLMReviewThemeProvider(ReplayTransport(V07 / f"{name}.jsonl"))
            results[label] = sc.with_providers(
                judgments=PrecomputedJudgmentProvider(served), review_themes=themes
            ).run()
        out[name] = {**d, "v09_strategies": strategies, "v09_results": results}
    return out


def _row(result, reference):
    report = evaluate_judgments(result.judgments, reference, reference_humans=True)
    return {t.type.value: (t.agreed, t.compared) for t in report.by_type}


def test_intent_risk_escalation_fixes_genre_browse_without_regressions(data):
    book = data["book_cozy_mystery"]
    ref = _human_reference("book_cozy_mystery", book["fixture"], book["fast"])
    rows = {label: _row(r, ref) for label, r in book["v09_results"].items()}
    assert rows["v0.8 routing"]["intent"] == (3, 4)
    assert rows["intent-risk escalation (v0.9)"]["intent"] == (4, 4)
    for kind in ("relevance", "entity", "equivalence"):  # no regression elsewhere
        assert rows["intent-risk escalation (v0.9)"][kind] == rows["v0.8 routing"][kind]
    escalated = {
        (t, s): r for t, s, r in book["v09_strategies"]["intent-risk escalation (v0.9)"].escalated
    }
    assert escalated[("intent", "small town mystery")] == "genre_browse"


def test_bottle_water_needs_the_prompt_not_routing(data):
    bottle = data["physical_water_bottle"]
    ref = _human_reference("physical_water_bottle", bottle["fixture"], bottle["fast"])
    for label, result in bottle["v09_results"].items():
        assert _row(result, ref)["intent"] == (4, 5), label  # both recorded tiers say informational
    escalated = {
        s for _, s, _ in bottle["v09_strategies"]["intent-risk escalation (v0.9)"].escalated
    }
    assert "bottle water" in escalated  # flagged, but the recorded strong answer agrees with fast


def test_structure_is_unchanged_across_strategies(data):
    for d in data.values():
        base = d["v09_results"]["v0.8 routing"]
        for result in d["v09_results"].values():
            assert [f.phrases for f in result.families.families] == [
                f.phrases for f in base.families.families
            ]
            assert {f.keyword for f in result.entity_flags} == {
                f.keyword for f in base.entity_flags
            }
            assert all(v.valid for v in result.validations)


# -- generated report ------------------------------------------------------------------


def _fmt(j):
    if j is None:
        return "-"
    r = thaw(j.result)
    return f"{r['label']} {r['score']:g}" if j.type is JudgmentType.INTENT else json.dumps(r)


def _money(v):
    return "unknown" if v is None else f"${v:.4f}"


def render(data) -> str:
    out = [
        "# v0.9 intent calibration (offline)",
        "",
        "> **No live calls.** Routing strategies are simulated from answers recorded live in "
        "v0.7 with prompt `judgment_batch-v2` (fast answers from production, strong answers "
        "from the strong comparison and production escalations) and fed through the real "
        "pipeline. The v0.9 prompt (`judgment_batch-v3`: intent separated from relevance, "
        "with the `bottle water` and genre examples) is **not** measured here: no answers "
        "exist for it yet. Costs are planner estimates for the current prompt.",
        "",
        "Reference: the **human-reviewed** reference (fixture judgments superseded by the "
        "decisions in `tests/fixtures/reviews/v08_human_decisions.json`).",
        "",
        "## Agreement with the human-reviewed reference",
        "",
        "| Scenario | Strategy | relevance | intent | entity | equivalence |",
        "|---|---|---|---|---|---|",
    ]
    for name, d in data.items():
        ref = _human_reference(name, d["fixture"], d["fast"])
        for label, result in d["v09_results"].items():
            row = _row(result, ref)
            cells = " | ".join(f"{row[k][0]}/{row[k][1]}" for k in TYPES)
            out.append(f"| {name} | {label} | {cells} |")
    out += [
        "",
        "## Intent judgments that differ from the human reference",
        "",
        "| Scenario | Keyword | Reference | Fast (v2) | Strong (v2) | Escalation signal (v0.9) |",
        "|---|---|---|---|---|---|",
    ]
    for name, d in data.items():
        ref = {
            (j.type.value, j.subject): j
            for j in _human_reference(name, d["fixture"], d["fast"])
            if j.type is JudgmentType.INTENT
        }
        fast = {(j.type.value, j.subject): j for j in d["fast"]}
        strong = {(j.type.value, j.subject): j for j in d["strong_pool"]}
        signals = {
            (t, s): r for t, s, r in d["v09_strategies"]["intent-risk escalation (v0.9)"].escalated
        }
        for key, r in sorted(ref.items()):
            f = fast.get(key)
            s = strong.get(key)
            if f is None or (f.label == r.label and (s is None or s.label == r.label)):
                continue
            out.append(
                f"| {name} | {key[1]} | {_fmt(r)} | {_fmt(f)} | {_fmt(s)} | "
                f"{signals.get(key, '-')} |"
            )
    out += [
        "",
        "## Intent escalations, strong-tier items and cost (keyword and equivalence stages)",
        "",
        "| Scenario | Strategy | Intent items escalated | Strong-tier items "
        "| Calls (fast / strong) | Expected cost | Worst case |",
        "|---|---|---|---|---|---|---|",
    ]
    for name, d in data.items():
        for label, outcome in d["v09_strategies"].items():
            kwargs = STRATEGIES[label]
            cost = strategy_cost(
                d["stages"],
                outcome,
                strong_types=kwargs.get("strong_types", ()),
                policy=kwargs["policy"],
            )
            intents = [s for t, s, _ in outcome.escalated if t == "intent"]
            out.append(
                f"| {name} | {label} | {', '.join(intents) or '-'} | {outcome.strong_items} | "
                f"{cost.planned_calls} ({cost.fast_calls} / {cost.strong_calls}) | "
                f"{_money(cost.expected_cost_usd)} | {_money(cost.worst_case_cost_usd)} |"
            )
    out += ["", "## Downstream effects vs v0.8 routing", ""]
    for name, d in data.items():
        base = d["v09_results"]["v0.8 routing"]
        base_rank = {s.keyword: i + 1 for i, s in enumerate(base.ranked)}
        for label, result in d["v09_results"].items():
            if label == "v0.8 routing":
                continue
            moved = [
                f"{s.keyword} {base_rank.get(s.keyword, '-')}->{i + 1}"
                for i, s in enumerate(result.ranked)
                if base_rank.get(s.keyword) != i + 1
            ]
            same_recs = [r.keyword for r in result.recommendations] == [
                r.keyword for r in base.recommendations
            ]
            same_backend = [str(p.value) for p in result.proposals] == [
                str(p.value) for p in base.proposals
            ]
            recs = "unchanged" if same_recs else [r.keyword for r in result.recommendations]
            backend = "unchanged" if same_backend else [str(p.value) for p in result.proposals]
            out.append(
                f"- {name}, {label}: rank moves {moved or 'none'}; recommendations {recs}; "
                f"backend {backend}."
            )
    out.append("")
    return "\n".join(out)


def test_intent_report_is_current(data):
    check(ROOT / "docs" / "baselines" / "intent_v0.9.md", render(data))
