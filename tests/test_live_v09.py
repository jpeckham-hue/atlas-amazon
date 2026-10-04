"""v0.9 LIVE confirmation: the v0.9 prompt and routing, recorded, replayed offline.

tests/fixtures/recordings/live/v09/ holds REAL exchanges recorded on
2026-10-04 through Vercel AI Gateway (routed to Anthropic) with
`scripts/record_live_baseline.py --dir v09 --production-only`: prompt
`judgment_batch-v3`, v0.9 escalation (relevance and intent risk signals).
Replay never touches the network (sockets are blocked here).

docs/baselines/live_v0.9.md is generated from these replays and must stay
current:

    ATLAS_REGEN_EXAMPLES=1 pytest tests/test_live_v09.py
"""

import socket
from collections import Counter

import pytest

from atlas_amazon.jsonvalue import thaw
from atlas_amazon.judgments import JudgmentRequest, JudgmentType
from atlas_amazon.report import report_json
from atlas_amazon.research import load_scenario
from atlas_amazon.semantic import (
    BatchedJudgmentProvider,
    LLMReviewThemeProvider,
    ReplayTransport,
    UsageLedger,
    evaluate_judgments,
    find_secrets,
)
from atlas_amazon.semantic.records import ChecksummedJsonl
from atlas_amazon.semantic.review import human_judgments, load_review_decisions, supersede
from atlas_amazon.semantic.tiers import FAST, STRONG
from atlas_amazon.semantic.usage import measured_recording_cost
from semantic_helpers import HISTORICAL, RECORDINGS, SCENARIOS
from test_examples import ROOT, check
from test_live_baseline_v07 import replay as replay_v07
from test_v08_calibration import REVIEWS, _scenario_data

V09 = RECORDINGS / "live" / "v09"
NAMES = ["book_cozy_mystery", "physical_water_bottle"]
TYPES = ("relevance", "intent", "entity", "equivalence")
V08_LABEL = "A: risk escalation (v0.8 signals)"


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise OSError("network access is disabled in live-replay tests")

    monkeypatch.setattr(socket, "socket", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


def replay(name, ledger=None):
    transport = ReplayTransport(V09 / f"{name}.jsonl")
    ledger = ledger or UsageLedger()
    return (
        load_scenario(SCENARIOS / f"{name}.json")
        .with_providers(
            judgments=BatchedJudgmentProvider(transport, ledger=ledger),
            review_themes=LLMReviewThemeProvider(transport, ledger=ledger),
        )
        .run(config=HISTORICAL)
    )


def human_reference(name, judgments):
    fixture = load_scenario(SCENARIOS / f"{name}.json").run(config=HISTORICAL)
    provider = load_review_decisions(REVIEWS / "v08_human_decisions.json")[name]
    requests = [JudgmentRequest(j.type, j.input) for j in judgments]
    return supersede(fixture.judgments, human_judgments(provider, requests))


def agreement(name, result):
    report = evaluate_judgments(
        result.judgments, human_reference(name, result.judgments), reference_humans=True
    )
    return report, {t.type.value: (t.agreed, t.compared) for t in report.by_type}


def by(judgments):
    return {(j.type.value, j.subject): j for j in judgments if j.provider == "anthropic"}


# -- tests -------------------------------------------------------------------------


@pytest.mark.parametrize("name", NAMES)
def test_recordings_are_real_gateway_exchanges(name):
    records = ChecksummedJsonl(V09 / f"{name}.jsonl").read()
    assert len(records) == 5 and not find_secrets(records)
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
    assert all(not g.failures for g in usage.groups)
    prompts = {j.prompt_version for j in first.judgments if j.provider == "anthropic"}
    assert prompts == {"judgment_batch-v3"}


def test_measured_cost():
    costs = [measured_recording_cost(V09 / f"{n}.jsonl") for n in NAMES]
    assert [c.calls for c in costs] == [5, 5]
    assert sum(c.cost_usd for c in costs) == pytest.approx(0.076021)
    assert sum(c.cost_usd for c in costs) < 0.25


def test_the_two_intent_targets_are_fixed():
    bottle = by(replay("physical_water_bottle").judgments)[("intent", "bottle water")]
    assert (bottle.label, bottle.score) == ("transactional", 0.8)
    assert bottle.call["escalation"]["from_result"]["label"] == "transactional"  # fast was right
    book = by(replay("book_cozy_mystery").judgments)[("intent", "small town mystery")]
    assert (book.label, book.score) == ("commercial_investigation", 0.7)


def test_agreement_against_the_human_reference():
    _, book = agreement("book_cozy_mystery", replay("book_cozy_mystery"))
    _, bottle = agreement("physical_water_bottle", replay("physical_water_bottle"))
    assert book == {
        "relevance": (10, 11),
        "intent": (3, 4),
        "entity": (3, 3),
        "equivalence": (1, 1),
    }
    assert bottle == {
        "relevance": (12, 12),
        "intent": (5, 5),
        "entity": (6, 6),
        "equivalence": (2, 2),
    }


def test_known_disagreements_are_the_documented_ones():
    report, _ = agreement("book_cozy_mystery", replay("book_cozy_mystery"))
    found = {(t.type.value, d.subject) for t in report.by_type for d in t.disagreements}
    assert found == {
        ("relevance", "cozy mystery kindle unlimited"),  # entity-blocked; fixture not reviewed
        ("intent", "cozy mystery books"),  # over-corrected to browsing by the v3 prompt
    }


@pytest.mark.parametrize("name", NAMES)
def test_structure_entity_blocking_and_lineage(name):
    live = replay(name)
    v07 = replay_v07(name)
    assert [f.phrases for f in live.families.families] == [f.phrases for f in v07.families.families]
    assert {(f.keyword, f.label) for f in live.entity_flags} == {
        (f.keyword, f.label) for f in v07.entity_flags
    }
    assert all(v.valid for v in live.validations)
    calls = set(live.evidence.ids_by_kind["semantic_call"])
    assert all(
        j.call["call_evidence_id"] in calls for j in live.judgments if j.provider == "anthropic"
    )
    reviews = set(live.evidence.ids_by_kind["review_sample"])
    for item in (*live.review_themes.positives, *live.review_themes.complaints):
        assert set(item.theme.review_evidence_ids) <= reviews


# -- generated report ------------------------------------------------------------------


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


def _families(result):
    return [f.phrases for f in result.families.families]


def _blocked(result):
    return {f.keyword for f in result.entity_flags}


def render() -> str:
    out = [
        "# v0.9 live confirmation",
        "",
        f"> **LIVE results**, recorded 2026-10-04 through Vercel AI Gateway (routed to "
        f"Anthropic): fast tier `{FAST.model}`, strong tier `{STRONG.model}`, prompt "
        "`judgment_batch-v3`, v0.9 escalation. Production pipeline only. Costs are "
        "**measured** (API-reported tokens x list price). Regenerated offline by "
        "`tests/test_live_v09.py`. *v0.8* below is v0.8 routing simulated from the v0.7 "
        "recordings (v0.8 was never run live).",
        "",
        "## Measured usage",
        "",
        "| Scenario | API calls | Fast / strong | Escalations (reason) | Cache hits "
        "| Input tok | Output tok | Measured cost |",
        "|---|---|---|---|---|---|---|---|",
    ]
    results = {}
    total = 0.0
    for name in NAMES:
        live = replay(name)
        results[name] = live
        m = measured_recording_cost(V09 / f"{name}.jsonl")
        total += m.cost_usd
        u = live.semantic_usage
        reasons = Counter(
            j.call["escalation"]["reason"]
            for j in live.judgments
            if j.provider == "anthropic" and "escalation" in j.call
        )
        out.append(
            f"| {name} | {m.calls} | {u.fast_calls} / {u.strong_calls} | {u.escalations} "
            f"({', '.join(f'{k} {n}' for k, n in sorted(reasons.items()))}) | {u.cache_hits} | "
            f"{m.input_tokens} | {m.output_tokens} | ${m.cost_usd:.4f} |"
        )
    out += [
        f"| **total** | | | | | | | **${total:.4f}** |",
        "",
        "No item failures, refusals, transport errors or budget halts.",
        "",
        "## Agreement with the human-reviewed reference",
        "",
        "| Scenario | Version | relevance | intent | entity | equivalence |",
        "|---|---|---|---|---|---|",
    ]
    v08 = {name: _scenario_data(name)["results"][V08_LABEL] for name in NAMES}
    for name in NAMES:
        for label, result in (("v0.8 (simulated)", v08[name]), ("v0.9 live", results[name])):
            _, row = agreement(name, result)
            cells = " | ".join(f"{row[k][0]}/{row[k][1]}" for k in TYPES)
            out.append(f"| {name} | {label} | {cells} |")
    out += [
        "",
        "## Disagreements with the reference (v0.9 live)",
        "",
        "| Scenario | Type | Keyword | Reference | v0.9 live | Rationale |",
        "|---|---|---|---|---|---|",
    ]
    for name in NAMES:
        report, _ = agreement(name, results[name])
        live = by(results[name].judgments)
        for t in report.by_type:
            for d in t.disagreements:
                j = live.get((t.type.value, d.subject))
                out.append(
                    f"| {name} | {t.type.value} | {d.subject} | {d.reference} | {_fmt(j)} | "
                    f"{j.rationale if j else '-'} |"
                )
    out += ["", "## Intent labels", ""]
    out += ["| Scenario | v0.8 (simulated) | v0.9 live |", "|---|---|---|"]
    for name in NAMES:

        def dist(result):
            c = Counter(
                j.label
                for j in result.judgments
                if j.provider == "anthropic" and j.type is JudgmentType.INTENT
            )
            return ", ".join(f"{k} {n}" for k, n in sorted(c.items()))

        out.append(f"| {name} | {dist(v08[name])} | {dist(results[name])} |")
    out += ["", "## Downstream outputs: v0.8 (simulated) vs v0.9 live", ""]
    for name in NAMES:
        old, new = v08[name], results[name]
        out += [f"### {name}", "", "| # | v0.8 (simulated) | v0.9 live |", "|---|---|---|"]
        for i in range(max(len(old.ranked), len(new.ranked))):
            a = (
                f"{old.ranked[i].keyword} ({old.ranked[i].score:.3f})"
                if i < len(old.ranked)
                else ""
            )
            b = (
                f"{new.ranked[i].keyword} ({new.ranked[i].score:.3f})"
                if i < len(new.ranked)
                else ""
            )
            out.append(f"| {i + 1} | {a} | {b} |")

        def same(a, b):
            return "unchanged" if a == b else "changed"

        out += [
            "",
            f"- Keyword families: {same(_families(old), _families(new))}.",
            f"- Entity blocking: {same(_blocked(old), _blocked(new))} "
            f"({sorted((f.keyword, f.label) for f in new.entity_flags)}).",
            f"- Recommendations: v0.8 {[r.keyword for r in old.recommendations]}; "
            f"v0.9 {[r.keyword for r in new.recommendations]}.",
            f"- Backend proposal: v0.8 `{[str(p.value) for p in old.proposals]}`; "
            f"v0.9 `{[str(p.value) for p in new.proposals]}`; passes audit: "
            f"{all(v.valid for v in new.validations)}.",
            f"- Review themes: positives {[i.theme.theme for i in new.review_themes.positives]}, "
            f"complaints {[i.theme.theme for i in new.review_themes.complaints]}; opportunities "
            f"(theme, first-party support) "
            f"{[(o.theme, bool(o.first_party_support)) for o in new.review_themes.opportunities]}.",
            "",
        ]
    return "\n".join(out)


def test_live_v09_report_is_current():
    check(ROOT / "docs" / "baselines" / "live_v0.9.md", render())
