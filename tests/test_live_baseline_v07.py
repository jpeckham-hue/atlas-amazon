"""v0.7 LIVE semantic baseline: real responses with first-party context, replayed offline.

tests/fixtures/recordings/live/v07/ holds REAL exchanges recorded on
2026-10-04 through Vercel AI Gateway (routed to Anthropic) by
`scripts/record_live_baseline.py`:

* `<scenario>.jsonl`: the production pipeline (fast tier, risk-signal
  escalation to the strong tier);
* `<scenario>.strong_comparison.jsonl`: the strong tier asked the same
  relevance and intent judgments, for evaluation only (never part of a run).

Replay never touches the network (sockets are blocked here).
docs/baselines/live_v0.7.md is generated from these replays plus the v0.6
recordings, and must stay current:

    ATLAS_REGEN_EXAMPLES=1 pytest tests/test_live_baseline_v07.py
"""

import re
import socket
from collections import Counter

import pytest

from atlas_amazon.jsonvalue import thaw
from atlas_amazon.judgments import JudgmentType
from atlas_amazon.report import report_json
from atlas_amazon.research import load_scenario
from atlas_amazon.semantic import (
    BatchedJudgmentProvider,
    EscalationPolicy,
    LLMReviewThemeProvider,
    ReplayTransport,
    UsageLedger,
    evaluate_judgments,
    find_secrets,
)
from atlas_amazon.semantic.comparison import (
    STRONG_EVAL_PROVIDER,
    evaluate_tier_comparison,
    run_strong_comparison,
)
from atlas_amazon.semantic.escalation import lexical_relevance, stated_feature
from atlas_amazon.semantic.recorded import final_judgments, recorded_judgments
from atlas_amazon.semantic.records import ChecksummedJsonl
from atlas_amazon.semantic.tiers import FAST, STRONG
from atlas_amazon.semantic.usage import measured_recording_cost
from semantic_helpers import HISTORICAL, RECORDINGS, SCENARIOS
from test_examples import ROOT, check

V07 = RECORDINGS / "live" / "v07"
V06 = RECORDINGS / "live"
NAMES = ["book_cozy_mystery", "physical_water_bottle"]
COMPARED = (JudgmentType.RELEVANCE, JudgmentType.INTENT)
FOCUS = {
    "book_cozy_mystery": ["amateur sleuth", "harbor town"],
    "physical_water_bottle": ["double wall vacuum", "leak proof"],
}


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise OSError("network access is disabled in live-replay tests")

    monkeypatch.setattr(socket, "socket", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


# The prompt and policy these recordings were made with (v0.8 added
# relevance-risk signals, v0.9 intent-risk signals and prompt judgment_batch-v3).
V07_POLICY = EscalationPolicy(relevance_risks=False, intent_risks=False)
V07_PROMPT = "judgment_batch-v2"


def replay(name, ledger=None):
    transport = ReplayTransport(V07 / f"{name}.jsonl")
    ledger = ledger or UsageLedger()
    return (
        load_scenario(SCENARIOS / f"{name}.json")
        .with_providers(
            judgments=BatchedJudgmentProvider(
                transport, ledger=ledger, escalation=V07_POLICY, prompt_version=V07_PROMPT
            ),
            review_themes=LLMReviewThemeProvider(transport, ledger=ledger),
        )
        .run(config=HISTORICAL)
    )


def comparison(name, result):
    return run_strong_comparison(
        ReplayTransport(V07 / f"{name}.strong_comparison.jsonl"),
        result.judgments,
        marketplace=result.metadata.marketplace,
        run_id=result.metadata.run_id,
        types=COMPARED,
        prompt_version=V07_PROMPT,
    )


def fixture_run(name):
    return load_scenario(SCENARIOS / f"{name}.json").run(config=HISTORICAL)


def v06_final(name, fixture):
    rules = [j for j in fixture.judgments if j.provider == "rules"]
    recorded = recorded_judgments(V06 / f"{name}.jsonl", prompt_version="judgment_batch-v1")
    return final_judgments(recorded) + rules


def files(name):
    return [V07 / f"{name}.jsonl", V07 / f"{name}.strong_comparison.jsonl"]


# -- tests ---------------------------------------------------------------------


@pytest.mark.parametrize("name", NAMES)
def test_recordings_are_real_gateway_exchanges(name):
    for path in files(name):
        records = ChecksummedJsonl(path).read()
        assert records and not find_secrets(records)
        for r in records:
            assert r["response"]["synthetic"] is False
            assert r["response"]["transport"] == "vercel-ai-gateway"
            assert r["response"]["model"] in (FAST.model, STRONG.model)
            assert r["request"]["providerOptions"] == {"gateway": {"only": ["anthropic"]}}


@pytest.mark.parametrize("name", NAMES)
def test_replay_is_complete_reproducible_and_offline(name):
    first, second = replay(name), replay(name)
    assert report_json(first) == report_json(second)
    usage = first.semantic_usage
    assert usage.live_calls == 0 and usage.replayed_calls == 5
    assert all("replay_miss" not in g.failures and not g.failures for g in usage.groups)


@pytest.mark.parametrize("name", NAMES)
def test_requests_carried_first_party_context(name):
    result = replay(name)
    contexts = {
        str(sorted(thaw(j.input["context"])))
        for j in result.judgments
        if j.provider == "anthropic" and j.type is not JudgmentType.EQUIVALENCE
    }
    [keys] = contexts
    assert "features" in keys and "description" in keys and "category" in keys


def test_measured_cost_and_tiers():
    costs = {n: [measured_recording_cost(p) for p in files(n)] for n in NAMES}
    total = sum(m.cost_usd for ms in costs.values() for m in ms)
    assert total == pytest.approx(0.131685)
    assert total < 0.25
    for name in NAMES:
        production, compare = costs[name]
        assert production.calls == 5 and compare.calls == 1
        assert compare.by_model == {STRONG.model: 1}


@pytest.mark.parametrize(
    ("name", "escalated"),
    [
        (
            "book_cozy_mystery",
            {
                ("equivalence", "cozy mystery books || mystery books cozy", "equivalence_conflict"),
                ("relevance", "amateur sleuth", "lexical_disagreement"),
            },
        ),
        (
            "physical_water_bottle",
            {
                ("relevance", "bottle water", "lexical_disagreement"),
                ("relevance", "hydra water bottle", "lexical_disagreement"),
            },
        ),
    ],
)
def test_escalations_were_risk_signals_not_confidence(name, escalated):
    result = replay(name)
    found = {
        (j.type.value, j.subject, j.call["escalation"]["reason"])
        for j in result.judgments
        if j.provider == "anthropic" and "escalation" in j.call
    }
    assert found == escalated
    for j in result.judgments:
        if j.provider == "anthropic" and "escalation" in j.call:
            assert j.model == STRONG.model and j.call["escalation"]["from_confidence"] >= 0.8


@pytest.mark.parametrize("name", NAMES)
def test_strong_comparison_preserves_both_answers(name):
    result = replay(name)
    comp = comparison(name, result)
    assert comp.strong and len(comp.strong) == len(comp.production)
    assert {j.provider for j in comp.strong} == {STRONG_EVAL_PROVIDER}
    assert {j.type for j in comp.strong} <= set(COMPARED)
    # Production judgments in the run are exactly the replayed ones: never overwritten.
    run_ids = {j.evidence_id for j in result.judgments}
    assert all(j.evidence_id in run_ids for j in comp.production)
    assert not {j.evidence_id for j in comp.strong} & run_ids


@pytest.mark.parametrize("name", NAMES)
def test_downstream_structure_and_lineage(name):
    live, fixture = replay(name), fixture_run(name)
    assert [f.phrases for f in live.families.families] == [
        f.phrases for f in fixture.families.families
    ]
    assert {f.keyword for f in live.entity_flags} == {f.keyword for f in fixture.entity_flags}
    assert all(v.valid for v in live.validations)
    calls = set(live.evidence.ids_by_kind["semantic_call"])
    for j in live.judgments:
        if j.provider == "anthropic":
            assert j.call["call_evidence_id"] in calls
    for d in live.derivations:
        if d.signals:
            for eid in d.signals.relevance.evidence_ids:
                assert eid in live.evidence.ids_by_kind["judgment"]
    themes = live.review_themes
    assert themes is not None and themes.complaints
    for item in (*themes.positives, *themes.complaints):
        reviews = set(live.evidence.ids_by_kind["review_sample"])
        assert item.theme.review_evidence_ids  # every theme cites stored review evidence
        assert set(item.theme.review_evidence_ids) <= reviews
        assert item.theme.evidence_id in live.evidence.ids_by_kind["review_theme"]


# -- generated report ----------------------------------------------------------


def _m(value):
    return "unknown" if value is None else f"${value:.4f}"


def _by(judgments, kinds=None):
    return {(j.type.value, j.subject): j for j in judgments if kinds is None or j.type in kinds}


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


def _agrees(a, b):
    if a is None or b is None:
        return None
    if a.type is JudgmentType.RELEVANCE:
        return abs(a.score - b.score) <= 0.2
    return (
        thaw(a.result) == thaw(b.result)
        if a.type is not JudgmentType.INTENT
        else (a.label == b.label)
    )


def _context_only_words(context):
    """Content words the v0.7 context added (not in the v0.6 title + seeds)."""
    stop = {"the", "a", "an", "and", "or", "for", "with", "of", "in", "to", "on", "her", "his"}

    def words(texts):
        return {w for t in texts for w in re.findall(r"[a-z]+", str(t).lower()) if w not in stop}

    old = words([context["product_title"], *context["seeds"]])
    added = words(
        [*context.get("features", ()), context.get("description", ""), context.get("subtitle", "")]
    )
    return added - old


def _source(v06, v07, context):
    """Heuristic attribution of a v0.6 -> v0.7 change (see the report's note)."""
    sources = []
    if v07.call and "escalation" in v07.call:
        sources.append("escalation (strong model)")
    keyword = v07.input.get("keyword", "")
    old_ctx = {"product_title": context["product_title"], "seeds": context["seeds"]}
    cited = set(re.findall(r"[a-z]+", v07.rationale.lower())) & _context_only_words(context)
    if (
        v07.type is JudgmentType.RELEVANCE
        and (
            stated_feature(keyword, context)
            or lexical_relevance(keyword, context) > lexical_relevance(keyword, old_ctx)
        )
    ) or len(cited) >= 2:
        sources.append("first-party context")
    if v07.type is JudgmentType.INTENT and not sources:
        sources.append("prompt change (intent guidance)")
    if not sources:
        sources.append("prompt/context change (not separable from run-to-run variation)")
    return " + ".join(sources)


def _phrases(result):
    return [f.phrases for f in result.families.families]


def _supported(result):
    return [(o.theme, bool(o.first_party_support)) for o in result.review_themes.opportunities]


def _agreement_row(report):
    return {t.type.value: (t.agreed, t.compared) for t in report.by_type}


def render(names) -> str:
    out = [
        "# v0.7 live semantic baseline",
        "",
        "> **LIVE results**, recorded 2026-10-04 through Vercel AI Gateway (routed to "
        f"Anthropic): fast tier `{FAST.model}`, strong tier `{STRONG.model}`. Costs are "
        "**measured** (API-reported tokens x list price). v0.6 figures are re-derived from "
        "the committed v0.6 live recordings. Regenerated offline by "
        "`tests/test_live_baseline_v07.py`.",
        "",
        "What changed from v0.6: keyword judgments receive the seller's first-party "
        "context (features, subtitle, description, category, brand); prompt "
        "`judgment_batch-v2` treats stated context as fact and gives browse-vs-buy intent "
        "guidance; escalation uses deterministic risk signals instead of confidence.",
        "",
        "## Measured usage",
        "",
        "| Scenario | Production calls | Comparison calls | Fast / strong | Escalations "
        "| Input tok | Output tok | Measured cost |",
        "|---|---|---|---|---|---|---|---|",
    ]
    data = {}
    total = 0.0
    for name in names:
        ledger = UsageLedger()
        live = replay(name, ledger)
        comp = comparison(name, live)
        fixture = fixture_run(name)
        v06 = v06_final(name, fixture)
        data[name] = (live, comp, fixture, v06)
        prod_cost, comp_cost = (measured_recording_cost(p) for p in files(name))
        total += prod_cost.cost_usd + comp_cost.cost_usd
        u = live.semantic_usage
        out.append(
            f"| {name} | {prod_cost.calls} | {comp_cost.calls} | "
            f"{u.fast_calls} / {u.strong_calls + comp_cost.calls} | {u.escalations} | "
            f"{prod_cost.input_tokens + comp_cost.input_tokens} | "
            f"{prod_cost.output_tokens + comp_cost.output_tokens} | "
            f"{_m(prod_cost.cost_usd + comp_cost.cost_usd)} |"
        )
    out += [
        f"| **total** | | | | | | | **{_m(total)}** |",
        "",
        "No item failures, refusals, transport errors, cache hits or budget halts. "
        "(A first attempt stalled at the gateway before any response and was billed "
        "nothing, as the gateway credit balance confirmed; the transport now times out "
        "after 120 s per attempt.)",
        "",
        "## Agreement with the fixture judgments",
        "",
        "Per type, agreed / compared. Relevance agrees when the scores differ by at most "
        "0.2. *Strong tier* is the evaluation-only comparison on relevance and intent.",
        "",
        "| Scenario | Type | v0.6 live | v0.7 live (production) | v0.7 strong tier |",
        "|---|---|---|---|---|",
    ]
    for name in names:
        live, comp, fixture, v06 = data[name]
        r06 = _agreement_row(evaluate_judgments(v06, fixture.judgments))
        r07 = _agreement_row(evaluate_judgments(live.judgments, fixture.judgments))
        tiers = evaluate_tier_comparison(comp, fixture.judgments)
        rs = _agreement_row(tiers.strong)
        for kind in ("relevance", "intent", "entity", "equivalence"):

            def cell(row, kind=kind):
                agreed, compared = row.get(kind, (0, 0))
                return f"{agreed}/{compared}" if compared else "-"

            out.append(
                f"| {name} | {kind} | {cell(r06)} | {cell(r07)} | "
                f"{cell(rs) if kind in ('relevance', 'intent') else 'not run'} |"
            )
    out += ["", "## Intent labels (all live intent judgments)", ""]
    out += ["| Scenario | v0.6 | v0.7 production | v0.7 strong tier |", "|---|---|---|---|"]
    for name in names:
        live, comp, fixture, v06 = data[name]

        def dist(js):
            c = Counter(j.label for j in js if j.type is JudgmentType.INTENT)
            return ", ".join(f"{k} {n}" for k, n in sorted(c.items()))

        prod = [j for j in live.judgments if j.provider == "anthropic"]
        out.append(f"| {name} | {dist(v06)} | {dist(prod)} | {dist(comp.strong)} |")
    out += [
        "",
        "## Focus keywords",
        "",
        "| Scenario | Keyword | Type | Fixture | v0.6 | v0.7 production | v0.7 strong | "
        "v0.7 rationale |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for name in names:
        live, comp, fixture, v06 = data[name]
        f_, o_, n_, s_ = (
            _by(fixture.judgments),
            _by(v06),
            _by(live.judgments),
            _by(comp.strong),
        )
        for keyword in FOCUS[name]:
            for kind in ("relevance", "intent"):
                key = (kind, keyword)
                new = n_.get(key)
                out.append(
                    f"| {name} | {keyword} | {kind} | {_fmt(f_.get(key))} | {_fmt(o_.get(key))} "
                    f"| {_fmt(new)} | {_fmt(s_.get(key))} | {new.rationale if new else '-'} |"
                )
    out += [
        "",
        "## Every judgment that changed from v0.6 to v0.7",
        "",
        "Source is a heuristic attribution: *escalation* when the v0.7 answer came from "
        "the strong tier after a risk signal; *first-party context* when the keyword is "
        "stated in or better supported by the context v0.7 added, or the model's "
        "rationale cites wording that only the new context contains; otherwise the "
        "prompt change, which a single run cannot separate from run-to-run variation. "
        "*Strong agrees with fixture* shows whether the evaluation-only strong answer "
        "matches the fixture (relevance and intent only).",
        "",
        "| Scenario | Type | Keyword | Fixture | v0.6 | v0.7 | Closer to fixture? | Source "
        "| Strong agrees with fixture |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for name in names:
        live, comp, fixture, v06 = data[name]
        f_, o_, n_, s_ = (
            _by(fixture.judgments),
            _by(v06),
            _by([j for j in live.judgments if j.provider == "anthropic"]),
            _by(comp.strong),
        )
        context = next(
            thaw(j.input["context"])
            for j in live.judgments
            if j.provider == "anthropic" and j.type is not JudgmentType.EQUIVALENCE
        )
        for key in sorted(n_):
            new, old = n_[key], o_.get(key)
            if old is None or _fmt(old) == _fmt(new):
                continue
            ref = f_.get(key)
            a_old, a_new = _agrees(old, ref), _agrees(new, ref)
            closer = (
                "-"
                if ref is None
                else "yes"
                if a_new and not a_old
                else "no (now disagrees)"
                if a_old and not a_new
                else "same"
            )
            strong = s_.get(key)
            strong_ok = (
                "-" if strong is None or ref is None else ("yes" if _agrees(strong, ref) else "no")
            )
            out.append(
                f"| {name} | {key[0]} | {key[1]} | {_fmt(ref)} | {_fmt(old)} | {_fmt(new)} | "
                f"{closer} | {_source(old, new, context)} | {strong_ok} |"
            )
    out += ["", "## Downstream outputs: v0.6 live vs v0.7 live", ""]
    for name in names:
        live, comp, fixture, v06 = data[name]
        lr = live.ranked
        out += [f"### {name}", "", "| # | Fixture ranking | v0.7 live ranking |", "|---|---|---|"]
        fr = fixture.ranked
        for i in range(max(len(fr), len(lr))):
            a = f"{fr[i].keyword} ({fr[i].score:.3f})" if i < len(fr) else ""
            b = f"{lr[i].keyword} ({lr[i].score:.3f})" if i < len(lr) else ""
            out.append(f"| {i + 1} | {a} | {b} |")
        out += [
            "",
            f"- Keyword families unchanged vs fixture: {_phrases(live) == _phrases(fixture)}.",
            f"- Entity flags: {sorted((f.keyword, f.label) for f in live.entity_flags)} "
            f"(fixture {sorted((f.keyword, f.label) for f in fixture.entity_flags)}).",
            f"- Recommendations: {[r.keyword for r in live.recommendations]} "
            f"(fixture {[r.keyword for r in fixture.recommendations]}).",
            f"- Backend proposal: `{[str(p.value) for p in live.proposals]}` "
            f"(fixture `{[str(p.value) for p in fixture.proposals]}`); "
            f"passes audit: {all(v.valid for v in live.validations)}.",
            f"- Review themes: positives {[i.theme.theme for i in live.review_themes.positives]}, "
            f"complaints {[i.theme.theme for i in live.review_themes.complaints]}; "
            f"opportunities (theme, first-party support): {_supported(live)}.",
            "",
        ]
    return "\n".join(out)


def test_live_baseline_v07_report_is_current():
    check(ROOT / "docs" / "baselines" / "live_v0.7.md", render(NAMES))
