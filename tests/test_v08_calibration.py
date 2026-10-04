"""v0.8: relevance calibration, human-grounded review, routing strategies, theme support.

All offline. The strategy comparison re-uses answers recorded in v0.7
(tests/fixtures/recordings/live/v07/): fast-tier answers from the production
recordings and strong-tier answers from the strong comparison and production
escalations. Generated reports (must stay current):

* docs/baselines/calibration_v0.8.md
* docs/reviews/judgment_review_v0.8.md

    ATLAS_REGEN_EXAMPLES=1 pytest tests/test_v08_calibration.py
"""

import json
import socket
from collections import Counter

import pytest

from atlas_amazon.evidence import make_evidence
from atlas_amazon.jsonvalue import thaw
from atlas_amazon.judgments import JudgmentRequest, JudgmentType, judgment_evidence, parse_judgment
from atlas_amazon.judgments.context import product_context
from atlas_amazon.models import EvidenceKind, ProductInput
from atlas_amazon.recipes import load_recipe
from atlas_amazon.research import ResearchRun, load_scenario
from atlas_amazon.reviews import review_theme_evidence, summarize_review_themes
from atlas_amazon.semantic import (
    BatchedJudgmentProvider,
    EscalationPolicy,
    LLMReviewThemeProvider,
    ReplayTransport,
    UsageLedger,
    evaluate_judgments,
)
from atlas_amazon.semantic.escalation import relevance_risks
from atlas_amazon.semantic.recorded import final_judgments, recorded_judgments
from atlas_amazon.semantic.review import human_judgments, load_review_decisions, supersede
from atlas_amazon.semantic.strategies import (
    PrecomputedJudgmentProvider,
    simulate_strategy,
    strategy_cost,
)
from atlas_amazon.semantic.tiers import FAST, STRONG
from conftest import T0
from semantic_helpers import RECORDINGS, SCENARIOS
from test_examples import ROOT, check
from test_live_baseline_v07 import V07_POLICY, V07_PROMPT, comparison, replay
from test_semantic_batch import batch_transport, items_of, judge

# The v0.8 report evaluates v0.8's signals (v0.9 added intent-risk signals).
V08_POLICY = EscalationPolicy(intent_risks=False)

REVIEWS = SCENARIOS.parent / "reviews"
V07 = RECORDINGS / "live" / "v07"
NAMES = ["book_cozy_mystery", "physical_water_bottle"]
KEYWORD = (JudgmentType.RELEVANCE, JudgmentType.INTENT, JudgmentType.ENTITY)


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


def rel(keyword, name="book_cozy_mystery"):
    return JudgmentRequest.about_keyword(JudgmentType.RELEVANCE, keyword, context=context(name))


def reason(request, score, confidence=0.9):
    return EscalationPolicy().reason(
        request,
        status="ok",
        structured={"score": score, "confidence": confidence, "rationale": "x"},
    )


# -- 1. relevance-risk signals -------------------------------------------------


class TestRelevanceRisk:
    def test_setting_terms(self):
        for keyword in ("small town", "harbor town"):
            risks = [r.value for r, _ in relevance_risks(keyword, context("book_cozy_mystery"))]
            assert risks[0] == "setting_term"
        assert reason(rel("harbor town"), 0.8)[0].value == "setting_term"

    def test_broad_category_terms(self):
        assert reason(rel("mystery books"), 0.8)[0].value == "broad_category"
        bottle = rel("bottles", "physical_water_bottle")
        assert reason(bottle, 0.9)[0].value == "broad_category"

    def test_generic_head_terms(self):
        risks = relevance_risks("small town", context("book_cozy_mystery"))
        assert "generic_head_term" in [r.value for r, _ in risks]
        generic = next(d for r, d in risks if r.value == "generic_head_term")
        assert "small town mystery" in generic and len(risks) == 2  # every reason reported
        insulated = rel("insulated water", "physical_water_bottle")
        assert reason(insulated, 0.9)[0].value == "generic_head_term"

    def test_incidental_description_support(self):
        steel = rel("stainless steel", "physical_water_bottle")
        assert reason(steel, 0.85)[0].value == "incidental_description_support"

    def test_specific_or_low_scores_do_not_trigger(self):
        book, bottle = context("book_cozy_mystery"), context("physical_water_bottle")
        for keyword in ("cozy mystery", "cozy mystery books", "amateur sleuth"):
            assert relevance_risks(keyword, book) == []
        for keyword in ("leak proof", "double wall vacuum", "water bottle", "water bottle 32 oz"):
            assert relevance_risks(keyword, bottle) == []
            assert reason(rel(keyword, "physical_water_bottle"), 0.9) is None
        assert reason(rel("small town"), 0.4) is None  # low scores are not over-rating
        assert (
            EscalationPolicy(relevance_risks=False).reason(
                rel("small town"), status="ok", structured={"score": 0.9, "confidence": 0.9}
            )
            is None
        )

    def test_signals_route_to_the_strong_tier_without_rewriting_scores(self):
        def answer(request, kind, subject):
            if request["model"] == FAST.model:
                return {"score": 0.8, "confidence": 0.95, "rationale": "setting in title"}
            return {"score": 0.35, "confidence": 0.7, "rationale": "a setting, not a book"}

        transport = batch_transport(answer)
        p = BatchedJudgmentProvider(transport)
        _, judgments = judge(p, [rel("small town")])
        [j] = judgments
        assert j.score == 0.35 and j.model == STRONG.model  # the strong answer, not a formula
        assert j.call["escalation"]["reason"] == "setting_term"
        assert j.call["escalation"]["from_result"] == {"score": 0.8}


# -- 2. human review supersedes the reference without deleting history -------


def test_human_decision_supersedes_fixture_without_deleting_history(tmp_path):
    decisions = json.loads((REVIEWS / "v08_human_decisions.json").read_text(encoding="utf-8"))
    for entry in decisions["decisions"]:  # start from an undecided copy
        entry["decision"] = entry["rationale"] = None
    path = tmp_path / "decisions.json"
    path.write_text(json.dumps(decisions), encoding="utf-8")
    assert load_review_decisions(path) == {}  # nothing decided
    decisions |= {"reviewer": "tester", "decided_at": "2026-10-05T09:00:00+00:00"}
    decisions["decisions"][0] |= {"decision": {"score": 0.4}, "rationale": "Setting evidenced."}
    path.write_text(json.dumps(decisions), encoding="utf-8")
    providers = load_review_decisions(path)
    assert set(providers) == {"book_cozy_mystery"}

    fixture = load_scenario(SCENARIOS / "book_cozy_mystery.json").run()
    requests = [JudgmentRequest(j.type, j.input) for j in fixture.judgments]
    human = human_judgments(providers["book_cozy_mystery"], requests)
    assert [(j.subject, j.score, j.model) for j in human] == [("harbor town", 0.4, "human:tester")]
    reference = supersede(fixture.judgments, human)
    by = {(j.type.value, j.subject): j for j in reference}
    # Scored against the human reference, a 0.8 candidate now disagrees on harbor town.
    candidate = [j for j in fixture.judgments if not j.is_human and j.subject != "harbor town"]
    report = evaluate_judgments(candidate, reference, reference_humans=True)
    relevance = {t.type.value: t for t in report.by_type}["relevance"]
    assert "harbor town" in relevance.missing_from_candidate  # decided item is scored
    assert by[("relevance", "harbor town")].is_human
    assert by[("relevance", "small town")].provider == "fixture"  # untouched
    old = [
        j for j in fixture.judgments if j.subject == "harbor town" and j.type.value == "relevance"
    ]
    assert old and old[0].score == 0.2  # the fixture judgment itself is unchanged
    assert len(reference) == len(fixture.judgments)

    bad = json.loads(path.read_text(encoding="utf-8"))
    bad["decisions"][0]["rationale"] = ""
    path.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(ValueError):
        load_review_decisions(path)


# -- 3. relevance-only strong routing ----------------------------------------


def test_relevance_only_strong_strategy_routes_by_type():
    requests = [
        JudgmentRequest.about_keyword(k, "leak proof", context=context("physical_water_bottle"))
        for k in KEYWORD
    ]
    transport = batch_transport()
    p = BatchedJudgmentProvider(
        transport, strong_types={JudgmentType.RELEVANCE}, escalation=EscalationPolicy.disabled()
    )
    plan = p.plan(requests)
    assert [(c.tier, c.items) for c in plan.batches] == [("fast", 2), ("strong", 1)]
    _, judgments = judge(p, requests)
    assert [r["model"] for r in transport.requests] == [FAST.model, STRONG.model]
    assert [i["type"] for i in items_of(transport.requests[1])] == ["relevance"]
    tiers = {j.type.value: j.call["tier"] for j in judgments}
    assert tiers == {"relevance": "strong", "intent": "fast", "entity": "fast"}


# -- 4. review-theme feature matching ----------------------------------------


def _theme(label, terms, reviews):
    return review_theme_evidence(
        provider="t",
        theme=label,
        polarity="positive",
        reviews=reviews,
        terms=terms,
        extractor="m",
        extractor_version="v",
        rationale="r",
        marketplace="US",
        run_id=None,
        extracted_at=T0,
    )


def _review(asin, text, i):
    return make_evidence(
        provider="fixture",
        kind=EvidenceKind.REVIEW_SAMPLE,
        marketplace="US",
        retrieved_at=T0,
        payload={"asin": asin, "rating": 5, "text": text, "i": i},
        subject=asin,
    )


class TestThemeFeatureMatching:
    product = ProductInput(
        title="Acme Insulated Water Bottle",
        recipe_id="physical-product",
        asin="B0ACME0001",
        attributes={
            "features": [
                "Double wall vacuum insulation keeps drinks cold for 24 hours",
                "Fits most cup holders",
            ]
        },
    )

    def support(self, label, terms, texts):
        reviews = [_review("B0COMP0001", t, i) for i, t in enumerate(texts)]
        report = summarize_review_themes(
            [_theme(label, terms, reviews)], reviews, product=self.product, min_count=2
        )
        [opportunity] = report.opportunities
        return opportunity.first_party_support

    def test_label_and_terms_match_without_exact_wording(self):
        support = self.support(
            "keeps contents cold for long periods",
            ["keeps ice 24 hours", "stays cold all day"],
            ["Still icy after a day.", "Ice lasted overnight."],
        )
        assert support == ("Double wall vacuum insulation keeps drinks cold for 24 hours",)

    def test_review_words_only_count_alongside_a_theme_word(self):
        # 'cold' (theme) + 'drinks' recurring in reviews -> related feature.
        assert self.support(
            "nice and cold", ["chilly"], ["My drinks stay put.", "Drinks never warm up."]
        ) == ("Double wall vacuum insulation keeps drinks cold for 24 hours",)
        # Review words alone never create support, and title words never count.
        assert (
            self.support("great water bottle", ["water bottle"], ["Drinks cold.", "Drinks cold."])
            == ()
        )

    def test_no_claim_without_a_supplied_feature(self):
        assert self.support("lid leaks", ["leak proof"], ["Leaked.", "Leaks in bag."]) == ()


# -- 5. evaluation and the generated reports ----------------------------------


def _assessments():
    data = json.loads((REVIEWS / "v08_assessments.json").read_text(encoding="utf-8"))
    return data["assessments"]


def _proposed_reference(name, fixture):
    proposals = []
    by = {(j.type.value, j.subject): j for j in fixture.judgments}
    for a in _assessments():
        if a["scenario"] != name or a["proposed"] is None:
            continue
        ref = by[(a["type"], a["subject"])]
        proposals.append(
            parse_judgment(
                judgment_evidence(
                    provider="proposal",
                    request=JudgmentRequest(ref.type, ref.input),
                    result=a["proposed"],
                    confidence=None,
                    model="claude-proposed",
                    prompt_version="review-proposal-v1",
                    rationale=a["note"],
                    marketplace="US",
                    judged_at=T0,
                )
            )
        )
    return supersede(fixture.judgments, proposals)


def _human_reference(name, fixture, requests):
    providers = load_review_decisions(REVIEWS / "v08_human_decisions.json")
    if name not in providers:
        return None
    return supersede(fixture.judgments, human_judgments(providers[name], requests))


def _scenario_data(name):
    sc = load_scenario(SCENARIOS / f"{name}.json")
    production = replay(name)
    comp = comparison(name, production)
    fixture = sc.run()
    run_id = production.metadata.run_id
    recorded = recorded_judgments(
        V07 / f"{name}.jsonl", prompt_version="judgment_batch-v2", run_id=run_id
    )
    fast = final_judgments([r for r in recorded if r.requested_model == FAST.model])
    prod_strong = final_judgments([r for r in recorded if r.requested_model == STRONG.model])
    evidence = {r.evidence.id: r.evidence for r in recorded}
    evidence.update({e.id: e for e in comp.evidence if e.kind == EvidenceKind.JUDGMENT})
    strong_pool = list(comp.strong) + prod_strong
    policy = V08_POLICY
    strategies = {
        "v0.7 production (actual)": None,
        "A: risk escalation (v0.8 signals)": simulate_strategy(
            "A", fast, strong_pool, policy=policy
        ),
        "B: strong tier for all relevance": simulate_strategy(
            "B", fast, strong_pool, policy=policy, strong_types={JudgmentType.RELEVANCE}
        ),
    }
    run = ResearchRun(
        product=sc.product,
        listing=sc.listing,
        recipe_id=sc.product.recipe_id,
        run_id=sc.run_id,
        providers=sc.providers,
        store=__import__("atlas_amazon.evidence", fromlist=["x"]).InMemoryEvidenceStore(),
        started_at=sc.started_at,
    )
    stages = run.model_requests()
    results = {"v0.7 production (actual)": production}
    for label, outcome in strategies.items():
        if outcome is None:
            continue
        served = [evidence[j.evidence_id] for j in outcome.judgments]
        themes = LLMReviewThemeProvider(ReplayTransport(V07 / f"{name}.jsonl"))
        results[label] = sc.with_providers(
            judgments=PrecomputedJudgmentProvider(served), review_themes=themes
        ).run()
    return {
        "fixture": fixture,
        "production": production,
        "comp": comp,
        "fast": fast,
        "strategies": strategies,
        "results": results,
        "stages": stages,
        "context": context(name),
        "evidence": evidence,
        "strong_pool": strong_pool,
        "scenario": sc,
    }


@pytest.fixture(scope="module")
def data():
    return {name: _scenario_data(name) for name in NAMES}


def test_v08_signals_catch_the_v07_failure_mode(data):
    book = data["book_cozy_mystery"]["strategies"]["A: risk escalation (v0.8 signals)"]
    bottle = data["physical_water_bottle"]["strategies"]["A: risk escalation (v0.8 signals)"]
    caught = {(t, s): r for t, s, r in book.escalated + bottle.escalated}
    assert caught[("relevance", "small town")] == "setting_term"
    assert caught[("relevance", "harbor town")] == "setting_term"
    assert caught[("relevance", "mystery books")] == "broad_category"
    assert caught[("relevance", "stainless steel")] == "incidental_description_support"
    assert not book.missing_strong and not bottle.missing_strong


def test_strategies_keep_structure_and_lineage(data):
    for d in data.values():
        fixture = d["fixture"]
        for result in d["results"].values():
            assert [f.phrases for f in result.families.families] == [
                f.phrases for f in fixture.families.families
            ]
            assert {f.keyword for f in result.entity_flags} == {
                f.keyword for f in fixture.entity_flags
            }
            assert all(v.valid for v in result.validations)
            judgment_ids = set(result.evidence.ids_by_kind["judgment"])
            for dv in result.derivations:
                if dv.signals:
                    assert set(dv.signals.relevance.evidence_ids) <= judgment_ids


def _row(report):
    return {t.type.value: (t.agreed, t.compared) for t in report.by_type}


def _cell(row, kind):
    agreed, compared = row.get(kind, (0, 0))
    return f"{agreed}/{compared}" if compared else "-"


def _fmt(j):
    if j is None:
        return "-"
    r = thaw(j.result)
    if j.type is JudgmentType.RELEVANCE:
        return f"{r['score']:g}"
    if j.type is JudgmentType.INTENT:
        return f"{r['label']} {r['score']:g}"
    if j.type is JudgmentType.ENTITY:
        return f"{r['label']} ({r['entity']})" if r["entity"] else r["label"]
    return str(r["equivalent"]).lower()


def _money(v):
    return "unknown" if v is None else f"${v:.4f}"


def render_calibration(data) -> str:
    out = [
        "# v0.8 relevance calibration (offline)",
        "",
        "> **No live calls.** Strategies are simulated from answers recorded live in v0.7: "
        "fast-tier answers from the production recordings, strong-tier answers from the "
        "strong comparison and production escalations. A live escalation would batch "
        "different neighbours, so the strong answers are an approximation. Downstream "
        "results come from the real pipeline fed with each strategy's judgments. Costs are "
        "planner estimates (list prices), not measurements.",
        "",
        "References: **fixture** (original); **proposed** (fixture superseded by Claude's "
        "proposed corrections in `tests/fixtures/reviews/v08_assessments.json`, *not* a "
        "human decision); **human** (fixture superseded by recorded review decisions; "
        "shown once `tests/fixtures/reviews/v08_human_decisions.json` has decisions).",
        "",
        "## Risk signals on the v0.7 fast-tier answers",
        "",
        "| Scenario | Keyword | Fast score | Signal (v0.8) | Strong answer | Fixture |",
        "|---|---|---|---|---|---|",
    ]
    for name, d in data.items():
        outcome = d["strategies"]["A: risk escalation (v0.8 signals)"]
        fast = {(j.type.value, j.subject): j for j in d["fast"]}
        strong = {(j.type.value, j.subject): j for j in d["comp"].strong}
        fixture = {(j.type.value, j.subject): j for j in d["fixture"].judgments}
        for kind, subject, why in outcome.escalated:
            key = (kind, subject)
            out.append(
                f"| {name} | {subject} ({kind}) | {_fmt(fast.get(key))} | `{why}` | "
                f"{_fmt(strong.get(key))} | {_fmt(fixture.get(key))} |"
            )
    out += [
        "",
        "## Agreement per type, per strategy and reference",
        "",
        "| Scenario | Strategy | Reference | relevance | intent | entity | equivalence |",
        "|---|---|---|---|---|---|---|",
    ]
    human_seen = False
    for name, d in data.items():
        fixture = d["fixture"]
        proposed = _proposed_reference(name, fixture)
        for label, result in d["results"].items():
            requests = [JudgmentRequest(j.type, j.input) for j in result.judgments]
            human = _human_reference(name, fixture, requests)
            refs = [("fixture", fixture.judgments), ("proposed", proposed)]
            if human is not None:
                human_seen = True
                refs.append(("human", human))
            for ref_label, ref in refs:
                row = _row(
                    evaluate_judgments(result.judgments, ref, reference_humans=ref_label == "human")
                )
                out.append(
                    f"| {name} | {label} | {ref_label} | "
                    + " | ".join(
                        _cell(row, k) for k in ("relevance", "intent", "entity", "equivalence")
                    )
                    + " |"
                )
    if not human_seen:
        out += ["", "No human review decisions are recorded yet, so there is no *human* row."]
    out += [
        "",
        "## Cost and calls per strategy (keyword and equivalence stages)",
        "",
        "Review themes (one strong call per scenario) are the same in every strategy and "
        "not included. *Planned* counts the batches plus the escalation calls the "
        "simulation needed.",
        "",
        "| Scenario | Strategy | Calls (fast / strong) | Strong items | Expected cost "
        "| Worst case |",
        "|---|---|---|---|---|---|",
    ]
    for name, d in data.items():
        for label, outcome in d["strategies"].items():
            if outcome is None:
                usage = d["production"].semantic_usage
                prod = [g for g in usage.groups]
                fast_calls = sum(g.fast_calls for g in prod)
                strong_calls = sum(g.strong_calls for g in prod) - 1  # minus review themes
                out.append(
                    f"| {name} | {label} | {fast_calls + strong_calls} ({fast_calls} / "
                    f"{strong_calls}) | {usage.escalations} | measured, see live_v0.7.md | - |"
                )
                continue
            strong_types = {JudgmentType.RELEVANCE} if label.startswith("B") else set()
            cost = strategy_cost(
                d["stages"],
                outcome,
                strong_types=strong_types,
                policy=V08_POLICY,
                prompt_version=V07_PROMPT,
            )
            out.append(
                f"| {name} | {label} | {cost.planned_calls} ({cost.fast_calls} / "
                f"{cost.strong_calls}) | {outcome.strong_items} | "
                f"{_money(cost.expected_cost_usd)} | {_money(cost.worst_case_cost_usd)} |"
            )
    out += ["", "## Downstream effects per strategy", ""]
    for name, d in data.items():
        out += [
            f"### {name}",
            "",
            "| # | " + " | ".join(d["results"]) + " |",
            "|---|" + "---|" * len(d["results"]),
        ]
        ranked = [r.ranked for r in d["results"].values()]
        for i in range(max(len(r) for r in ranked)):
            cells = [f"{r[i].keyword} ({r[i].score:.3f})" if i < len(r) else "" for r in ranked]
            out.append(f"| {i + 1} | " + " | ".join(cells) + " |")
        out.append("")
        for label, result in d["results"].items():
            out.append(
                f"- {label}: recommendations {[r.keyword for r in result.recommendations]}; "
                f"backend `{[str(p.value) for p in result.proposals]}`"
            )
        out.append("")
    out += [
        "## Disagreement classification (Claude's assessment, pending human review)",
        "",
        "| Scenario | Type | Keyword | Class | Fixture | v0.7 fast | v0.7 strong | Proposed |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for a in _assessments():
        d = data[a["scenario"]]
        key = (a["type"], a["subject"])
        fixture = {(j.type.value, j.subject): j for j in d["fixture"].judgments}.get(key)
        fast = {(j.type.value, j.subject): j for j in d["fast"]}.get(key)
        strong = {(j.type.value, j.subject): j for j in d["comp"].strong}.get(key)
        proposed = "keep fixture" if a["proposed"] is None else json.dumps(a["proposed"])
        out.append(
            f"| {a['scenario']} | {a['type']} | {a['subject']} | {a['classification']} | "
            f"{_fmt(fixture)} | {_fmt(fast)} | {_fmt(strong)} | {proposed} |"
        )
    counts = Counter(a["classification"] for a in _assessments())
    out += [
        "",
        f"Totals: {dict(sorted(counts.items()))}. Details and every rationale: "
        "[docs/reviews/judgment_review_v0.8.md](../reviews/judgment_review_v0.8.md).",
        "",
    ]
    return "\n".join(out)


def render_review(data) -> str:
    out = [
        "# Judgment review queue (v0.8)",
        "",
        "Fixture judgments were written before judgments could see the seller's full "
        "first-party context. These are the open disagreements between the fixtures and "
        "the live models. **Atlas does not change the fixtures.** To record a decision, "
        "edit `tests/fixtures/reviews/v08_human_decisions.json` (set `decision` and "
        "`rationale`, plus `reviewer` and `decided_at`); decisions become `human` "
        "judgments that supersede the fixture as the evaluation reference, and all "
        "fixture and model judgments stay in the record.",
        "",
        "The *classification* and *proposed* values are Claude's assessment, not a decision.",
        "",
    ]
    for a in _assessments():
        d = data[a["scenario"]]
        key = (a["type"], a["subject"])

        def pick(js, key=key):
            return {(j.type.value, j.subject): j for j in js}.get(key)

        from test_live_baseline_v07 import v06_final

        rows = [
            ("fixture", pick(d["fixture"].judgments)),
            ("v0.6 live", pick(v06_final(a["scenario"], d["fixture"]))),
            ("v0.7 fast", pick(d["fast"])),
            ("v0.7 production", pick(d["production"].judgments)),
            ("v0.7 strong", pick(d["comp"].strong)),
        ]
        ctx = d["context"]
        out += [
            f"## {a['scenario']}: {a['subject']} ({a['type']})",
            "",
            f"- Classification: **{a['classification']}**; proposed: "
            f"{'keep fixture' if a['proposed'] is None else json.dumps(a['proposed'])}",
            f"- Assessment: {a['note']}",
            f"- First-party context: title *{ctx['product_title']}*"
            + (f", subtitle *{ctx['subtitle']}*" if ctx.get("subtitle") else "")
            + f"; seeds {ctx['seeds']}; features {ctx.get('features', [])}; "
            f'description: "{ctx.get("description", "")}"',
            "",
            "| Source | Judgment | Confidence | Rationale |",
            "|---|---|---|---|",
        ]
        for label, j in rows:
            if j is None:
                out.append(f"| {label} | - | - | - |")
            else:
                conf = "-" if j.confidence is None else f"{j.confidence:g}"
                out.append(f"| {label} | {_fmt(j)} | {conf} | {j.rationale} |")
        out.append("")
    return "\n".join(out)


def test_calibration_report_is_current(data):
    check(ROOT / "docs" / "baselines" / "calibration_v0.8.md", render_calibration(data))


def test_review_artifact_is_current(data):
    check(ROOT / "docs" / "reviews" / "judgment_review_v0.8.md", render_review(data))


def test_v07_replay_policy_pin_is_the_v07_behavior():
    assert V07_POLICY.relevance_risks is False and V07_POLICY.intent_risks is False
    assert V08_POLICY.relevance_risks is True and V08_POLICY.intent_risks is False
    assert UsageLedger is not None
