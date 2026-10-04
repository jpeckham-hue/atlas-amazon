"""Replay of the v0.10 live market slice (SP-API searchCatalogItems), offline.

The recordings in tests/fixtures/recordings/live/market_v10/ are written once
by `scripts/record_live_market.py --run` and never regenerated. Until they
exist these tests skip. Once they do, they check that replay reproduces the
same Evidence and downstream outputs with sockets blocked, that unsupported
feature keywords stay blocked, and that the report is current:

    ATLAS_REGEN_EXAMPLES=1 pytest tests/test_live_market_v10.py
"""

import socket

import pytest

from atlas_amazon.evidence import InMemoryEvidenceStore
from atlas_amazon.providers.sp_api import ReplayHttpTransport
from atlas_amazon.research import load_scenario
from semantic_helpers import RECORDINGS, SCENARIOS
from test_examples import check
from test_market_sp_api import load_runner

LIVE = RECORDINGS / "live" / "market_v10"
NAMES = ["book_cozy_mystery", "physical_water_bottle"]
RECORDED = [n for n in NAMES if (LIVE / f"{n}.jsonl").exists()]

pytestmark = pytest.mark.skipif(not RECORDED, reason="live market slice not recorded yet")


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise OSError("network access is disabled")

    monkeypatch.setattr(socket, "socket", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


def replay(name):
    runner = load_runner()
    sc = load_scenario(SCENARIOS / f"{name}.json")
    provider = runner.market_provider(ReplayHttpTransport(LIVE / f"{name}.jsonl"))
    store = InMemoryEvidenceStore()
    return provider, sc.with_providers(catalog_search=provider).run(store=store), store


@pytest.mark.parametrize("name", RECORDED)
def test_replay_is_exact_and_complete(name):
    first_provider, first, _ = replay(name)
    _, second, _ = replay(name)
    assert not [f for f in first_provider.failures if f[1] == "replay_miss"]
    assert first_provider.total_calls == 0  # replay never spends the live budget
    assert first.evidence.ids_by_kind == second.evidence.ids_by_kind
    assert first.metadata.evidence_fingerprint == second.metadata.evidence_fingerprint
    assert first.ranked == second.ranked
    assert first.recommendations == second.recommendations
    assert first.proposals == second.proposals
    assert first.unsupported_opportunities == second.unsupported_opportunities


@pytest.mark.parametrize("name", RECORDED)
def test_live_evidence_is_scoped_and_attributed(name):
    _, result, store = replay(name)
    searches = [store.get(i) for i in result.evidence.ids_by_kind.get("catalog_search", ())]
    assert searches, "no successful catalog search was recorded"
    for e in searches:
        assert e.provider == "sp-api-catalog" and e.marketplace == "US"
        assert e.payload["marketplace_id"] == "ATVPDKIKX0DER"
        assert e.source_url.startswith("https://sellingpartnerapi-na.amazon.com/")


@pytest.mark.parametrize("name", RECORDED)
def test_unsupported_terms_stay_blocked(name):
    _, result, _ = replay(name)
    blocked = {u.keyword for u in result.unsupported_opportunities}
    assert not blocked & {r.keyword for r in result.recommendations}
    if result.backend_plan:
        assert not blocked & set(result.backend_plan.packed_keywords)
    assert all(v.valid for v in result.validations)


def test_live_market_report_is_current():
    runner = load_runner()
    comparisons, failures, calls = {}, {}, 0
    for name in RECORDED:
        transport = ReplayHttpTransport(LIVE / f"{name}.jsonl")
        calls += len(transport)
        provider, comparisons[name] = runner.run_scenario(name, transport)
        failures[name] = list(provider.failures)
    check(runner.REPORT, runner.build_report(comparisons, calls, failures))
