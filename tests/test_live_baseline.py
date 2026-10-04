"""v0.6 LIVE semantic baseline: real model responses, replayed offline.

tests/fixtures/recordings/live/ holds REAL exchanges recorded on 2026-10-04
through Vercel AI Gateway (`scripts/record_live_baseline.py`), routed to
Anthropic: Claude Haiku 4.5 (fast tier) and Claude Sonnet 5.5 (strong tier).
Unlike tests/fixtures/recordings/*.jsonl (synthetic, scripted), nothing here
is fabricated. Replay never touches the network; these tests also block
sockets to prove it.

docs/baselines/live_v0.6.md is generated from the replay and must stay
current. Regenerate (offline) after an intentional change:

    ATLAS_REGEN_EXAMPLES=1 pytest tests/test_live_baseline.py

Never re-record over these files; `record_live_baseline.py` refuses to.
"""

import socket

import pytest

from atlas_amazon.report import report_json
from atlas_amazon.research import load_scenario
from atlas_amazon.semantic import (
    BatchedJudgmentProvider,
    LLMReviewThemeProvider,
    ReplayTransport,
    UsageLedger,
    evaluate_judgments,
    find_secrets,
    render_evaluation_markdown,
)
from atlas_amazon.semantic.records import ChecksummedJsonl
from atlas_amazon.semantic.tiers import FAST, STRONG
from atlas_amazon.semantic.usage import measured_recording_cost
from semantic_helpers import RECORDINGS, SCENARIOS
from test_examples import ROOT, check

LIVE = RECORDINGS / "live"
NAMES = ["book_cozy_mystery", "physical_water_bottle"]
RECORDED_ON = "2026-10-04"


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise OSError("network access is disabled in live-replay tests")

    monkeypatch.setattr(socket, "socket", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


def replay_live(name, ledger=None):
    transport = ReplayTransport(LIVE / f"{name}.jsonl")
    ledger = ledger or UsageLedger()
    return (
        load_scenario(SCENARIOS / f"{name}.json")
        .with_providers(
            judgments=BatchedJudgmentProvider(transport, ledger=ledger),
            review_themes=LLMReviewThemeProvider(transport, ledger=ledger),
        )
        .run()
    )


def fixture_run(name):
    return load_scenario(SCENARIOS / f"{name}.json").run()


@pytest.mark.parametrize("name", NAMES)
def test_recordings_are_real_gateway_exchanges(name):
    records = ChecksummedJsonl(LIVE / f"{name}.jsonl").read()
    assert records and not find_secrets(records)
    for r in records:
        response = r["response"]
        assert response["synthetic"] is False and response["transport"] == "vercel-ai-gateway"
        assert response["model"] in (FAST.model, STRONG.model)
        assert response["responded_at"].startswith(RECORDED_ON)
        assert r["request"]["providerOptions"] == {"gateway": {"only": ["anthropic"]}}
        assert response["usage"]["input_tokens"] > 0


@pytest.mark.parametrize("name", NAMES)
def test_replay_is_complete_reproducible_and_offline(name):
    first, second = replay_live(name), replay_live(name)
    assert report_json(first) == report_json(second)
    usage = first.semantic_usage
    assert usage.live_calls == 0
    assert usage.replayed_calls == len(ChecksummedJsonl(LIVE / f"{name}.jsonl").read())
    assert all("replay_miss" not in g.failures for g in usage.groups)
    model = [j for j in first.judgments if j.provider == "anthropic"]
    assert model and all(j.call["synthetic"] is False for j in model)
    assert {j.model for j in model} <= {FAST.model, STRONG.model}


def test_live_usage_matches_what_was_measured():
    book = measured_recording_cost(LIVE / "book_cozy_mystery.jsonl")
    bottle = measured_recording_cost(LIVE / "physical_water_bottle.jsonl")
    assert (book.calls, bottle.calls) == (3, 5)
    assert book.cost_usd == pytest.approx(0.022479)
    assert bottle.cost_usd == pytest.approx(0.033219)
    assert book.cost_usd + bottle.cost_usd < 0.25  # the hard cap of the run
    usage = replay_live("physical_water_bottle").semantic_usage
    assert (usage.fast_calls, usage.strong_calls, usage.escalations) == (3, 2, 2)
    assert usage.input_tokens == bottle.input_tokens
    assert usage.output_tokens == bottle.output_tokens


def test_silently_omitted_items_were_caught_and_escalated():
    """Haiku skipped 2 of 23 items in one batch; ID matching caught it, Sonnet answered."""
    ledger = UsageLedger()
    result = replay_live("physical_water_bottle", ledger)
    fast_failures = [r for r in ledger.records if r.tier == "fast" and r.item_failures]
    assert [dict(r.item_failures) for r in fast_failures] == [{"missing": 2}]
    escalated = [j for j in result.judgments if "escalation" in (j.call or {})]
    assert sorted((j.type.value, j.subject) for j in escalated) == [
        ("intent", "insulated water bottle"),
        ("relevance", "insulated water bottle"),
    ]
    for j in escalated:
        assert j.model == STRONG.model and j.call["escalation"]["reason"] == "failed"
        assert j.call["escalation"]["from_status"] == "missing"


@pytest.mark.parametrize("name", NAMES)
def test_structure_that_live_judgments_did_not_change(name):
    live, fixture = replay_live(name), fixture_run(name)
    assert [f.phrases for f in live.families.families] == [
        f.phrases for f in fixture.families.families
    ]
    assert {f.keyword for f in live.entity_flags} == {f.keyword for f in fixture.entity_flags}
    assert all(v.valid for v in live.validations)  # proposals still pass the audit


def test_strong_tier_probe_recording():
    [r] = ChecksummedJsonl(LIVE / "gateway_strong_probe.jsonl").read()
    assert r["request"]["thinking"] == {"type": "between_tools"}
    assert r["request"]["model"] == STRONG.model and r["response"]["text"] == '{"ok":true}'


# -- the generated baseline report --------------------------------------------


def _money(value):
    return "unknown" if value is None else f"${value:.4f}"


def _rank(result):
    return {s.keyword: i + 1 for i, s in enumerate(result.ranked)}


def _impact(subject, live, fixture):
    lr, fr = _rank(live), _rank(fixture)
    lrec = {r.keyword for r in live.recommendations}
    frec = {r.keyword for r in fixture.recommendations}
    lprop = set(live.backend_plan.packed_keywords) if live.backend_plan else set()
    fprop = set(fixture.backend_plan.packed_keywords) if fixture.backend_plan else set()
    parts = []
    if subject in lr or subject in fr:
        parts.append(f"rank {fr.get(subject, '-')} -> {lr.get(subject, '-')}")
    if (subject in lrec) != (subject in frec):
        parts.append("recommended" if subject in lrec else "no longer recommended")
    in_l = subject in lprop
    if in_l != (subject in fprop):  # packed_keywords: ranked keywords that added content
        parts.append("now packed in backend" if in_l else "no longer packed in backend")
    return "; ".join(parts) or "no ranking effect (unranked)"


def render_baseline(names) -> str:
    out = [
        "# v0.6 live semantic baseline",
        "",
        f"> **LIVE results.** Recorded {RECORDED_ON} through Vercel AI Gateway, routed to "
        'Anthropic (`providerOptions.gateway.only = ["anthropic"]`): fast tier '
        f"`{FAST.model}`, strong tier `{STRONG.model}`. Costs are **measured**: API-reported "
        "tokens of each recorded exchange times list price. This report is regenerated "
        "offline from the committed recordings (`tests/test_live_baseline.py`). The v0.5 "
        "benchmark (`docs/benchmarks/semantic_cost_v0.5.md`) remains a synthetic "
        "estimate.",
        "",
        "## Measured usage",
        "",
        "| Scenario | API calls | Fast / strong | Escalations | Cache hits | Input tok "
        "| Output tok | Measured cost | Item failures |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    total = 0.0
    results = {}
    for name in names:
        ledger = UsageLedger()
        live = replay_live(name, ledger)
        results[name] = live
        m = measured_recording_cost(LIVE / f"{name}.jsonl")
        u = live.semantic_usage
        total += m.cost_usd
        fails = {}
        for r in ledger.records:
            for k, n in r.item_failures:
                fails[k] = fails.get(k, 0) + n
        out.append(
            f"| {name} | {m.calls} | {u.fast_calls} / {u.strong_calls} | {u.escalations} | "
            f"{u.cache_hits} | {m.input_tokens} | {m.output_tokens} | {_money(m.cost_usd)} | "
            f"{', '.join(f'{k} {n}' for k, n in fails.items()) or 'none'} |"
        )
    out += [
        f"| **total** | | | | | | | **{_money(total)}** | |",
        "",
        "No refusals, malformed batches, transport errors or budget halts occurred.",
        "",
    ]
    for name in names:
        live, fixture = results[name], fixture_run(name)
        report = evaluate_judgments(
            live.judgments,
            fixture.judgments,
            candidate_label="live model",
            reference_label="fixture",
        )
        out += [f"## {name}", ""]
        out.append(render_evaluation_markdown(report).split("\n", 2)[2].strip())
        out += ["", "### Effect of each disagreement", ""]
        out += ["| Type | Keyword | Effect |", "|---|---|---|"]
        for t in report.by_type:
            for d in t.disagreements:
                out.append(
                    f"| {t.type.value} | {d.subject} | {_impact(d.subject, live, fixture)} |"
                )
        out += ["", "### Downstream outputs: fixture judgments vs live", ""]
        fr, lr = fixture.ranked, live.ranked
        out += ["| # | Fixture ranking | Live ranking |", "|---|---|---|"]
        for i in range(max(len(fr), len(lr))):
            a = f"{fr[i].keyword} ({fr[i].score:.3f})" if i < len(fr) else ""
            b = f"{lr[i].keyword} ({lr[i].score:.3f})" if i < len(lr) else ""
            out.append(f"| {i + 1} | {a} | {b} |")

        def same(a, b):
            return "unchanged" if a == b else "changed"

        ff = [f.phrases for f in fixture.families.families]
        lf = [f.phrases for f in live.families.families]
        out += [
            "",
            f"- Keyword families: {same(ff, lf)}.",
            "- Entity flags: fixture "
            f"{sorted((f.keyword, f.label) for f in fixture.entity_flags)}; live "
            f"{sorted((f.keyword, f.label) for f in live.entity_flags)}.",
            f"- Recommendations: fixture {[r.keyword for r in fixture.recommendations]}; "
            f"live {[r.keyword for r in live.recommendations]}.",
            f"- Backend proposal: fixture `{[str(p.value) for p in fixture.proposals]}`; "
            f"live `{[str(p.value) for p in live.proposals]}`.",
        ]
        for label, attr in (("positive", "positives"), ("complaint", "complaints")):
            out.append(
                f"- Repeated {label} themes: fixture "
                f"{[i.theme.theme for i in getattr(fixture.review_themes, attr)]}; live "
                f"{[i.theme.theme for i in getattr(live.review_themes, attr)]}."
            )

        def supported(result):
            return [
                (o.theme, bool(o.first_party_support)) for o in result.review_themes.opportunities
            ]

        out.append(
            "- Opportunities (theme, has first-party support): fixture "
            f"{supported(fixture)}; live {supported(live)}."
        )
        out.append("")
    return "\n".join(out)


def test_live_baseline_report_is_current():
    check(ROOT / "docs" / "baselines" / "live_v0.6.md", render_baseline(NAMES))
