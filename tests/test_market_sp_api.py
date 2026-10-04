"""v0.10: the SP-API catalog market-data adapter, fully offline.

Every test runs with sockets blocked. Live calls need ATLAS_ALLOW_LIVE_MARKET=1
and SP-API credentials, neither of which CI has.
"""

import json
import socket

import pytest

from atlas_amazon.evidence import InMemoryEvidenceStore
from atlas_amazon.providers.base import CatalogProvider, CatalogSearchProvider
from atlas_amazon.providers.sp_api import (
    LiveMarketDisabled,
    LiveSpApiTransport,
    RecordingHttpTransport,
    ReplayHttpTransport,
    SpApiCatalogProvider,
    UnsupportedMarketplace,
    render_market_plan,
)
from atlas_amazon.providers.sp_api.http import HttpTransportError
from atlas_amazon.research import load_scenario
from atlas_amazon.research.market import compare_market, render_market_comparison
from market_helpers import BOOK, BOTTLE, US, failure, fake_transport, params, sp_item
from semantic_helpers import SCENARIOS

NAMES = ["book_cozy_mystery", "physical_water_bottle"]


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise OSError("network access is disabled")

    monkeypatch.setattr(socket, "socket", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


def provider(transport, **kwargs):
    return SpApiCatalogProvider(transport, **kwargs)


def run(name, market=None, store=None):
    sc = load_scenario(SCENARIOS / f"{name}.json")
    if market is not None:
        sc = sc.with_providers(catalog_search=market)
    store = store if store is not None else InMemoryEvidenceStore()
    return sc.run(store=store), store


def of_kind(evidence, kind):
    return [e for e in evidence if e.kind == kind]


# -- response -> Evidence ------------------------------------------------------------


class TestConversion:
    def test_provider_satisfies_both_protocols(self):
        p = provider(fake_transport(BOOK))
        assert isinstance(p, CatalogProvider) and isinstance(p, CatalogSearchProvider)

    def test_catalog_item_payload(self):
        p = provider(fake_transport(BOTTLE))
        found = p.search(["water bottle"], marketplace="US", run_id="r1")
        item = next(e for e in of_kind(found, "catalog_item") if e.subject == "B0MKTW0001")
        assert item.provider == "sp-api-catalog"
        assert item.marketplace == "US" and item.run_id == "r1"
        assert item.retrieved_at.isoformat() == "2026-10-04T10:00:00+00:00"
        assert item.payload["title"] == "Summit Insulated Water Bottle with Straw Lid, 32 oz"
        assert item.payload["brand"] == "Summit"
        assert item.payload["bullets"] == (
            "Double wall vacuum insulation",
            "Leak proof straw lid",
            "BPA free",
        )
        assert item.payload["classifications"] == ("Fake Category",)
        assert item.payload["source"] == "sp-api:searchCatalogItems"
        assert item.payload["raw"]["asin"] == "B0MKTW0001"  # the item exactly as returned

    def test_catalog_search_record(self):
        p = provider(fake_transport(BOTTLE))
        found = p.search(["Water Bottle"], marketplace="US", run_id="r1")
        (search,) = of_kind(found, "catalog_search")
        assert search.subject == "water bottle"
        assert search.payload["result_asins"] == ("B0MKTW0001", "B0MKTW0002")
        assert search.payload["number_of_results"] == 2
        assert search.payload["marketplace_id"] == US
        assert search.payload["raw"]["items"][0]["asin"] == "B0MKTW0001"
        assert search.source_url.startswith(
            "https://sellingpartnerapi-na.amazon.com/catalog/2022-04-01/items?"
        )
        assert "keywords=water%2Cbottle" in search.source_url

    def test_request_shape_and_no_credentials_in_urls(self):
        transport = fake_transport(BOTTLE)
        found = provider(transport, page_size=5).search(["water bottle"], marketplace="US")
        p = params(transport.requests[0])
        assert p == {
            "includedData": "summaries,attributes,classifications,salesRanks",
            "keywords": "water,bottle",
            "marketplaceIds": US,
            "pageSize": "5",
        }
        for e in found:
            assert "token" not in e.source_url.lower() and "secret" not in e.source_url.lower()

    def test_get_items_uses_identifier_search(self):
        transport = fake_transport(BOTTLE)
        found = provider(transport).get_items(["B0MKTW0002", "B0MKTW0001"], marketplace="US")
        assert [e.subject for e in found] == ["B0MKTW0002", "B0MKTW0001"]
        assert params(transport.requests[0])["identifiersType"] == "ASIN"
        with pytest.raises(ValueError, match="invalid ASIN"):
            provider(transport).get_items(["nope"], marketplace="US")

    def test_identifier_lookups_are_grouped_by_twenty(self):
        transport = fake_transport(BOTTLE)
        asins = [f"B0MKTX{i:04d}" for i in range(25)]
        provider(transport).get_items(asins, marketplace="US")
        assert len(transport.requests) == 2

    def test_evidence_ids_are_deterministic(self):
        a = provider(fake_transport(BOOK)).search(["cozy mystery"], marketplace="US", run_id="r")
        b = provider(fake_transport(BOOK)).search(["cozy mystery"], marketplace="US", run_id="r")
        assert [e.id for e in a] == [e.id for e in b]
        c = provider(fake_transport(BOOK)).search(["cozy mystery"], marketplace="US", run_id="x")
        assert {e.id for e in a}.isdisjoint(e.id for e in c)


# -- duplicates, partial and malformed responses -------------------------------------------


class TestRobustness:
    def test_duplicate_asins_across_queries_recorded_once(self):
        found = provider(fake_transport(BOOK)).search(
            ["cozy mystery", "small town mystery"], marketplace="US", run_id="r"
        )
        subjects = [e.subject for e in of_kind(found, "catalog_item")]
        assert subjects.count("B0MKTB0001") == 1
        second = of_kind(found, "catalog_search")[1]
        assert "B0MKTB0001" in second.payload["result_asins"]  # still listed in that query

    def test_duplicate_item_within_one_response(self):
        dup = sp_item("B0MKTW0001", "Same bottle")
        found = provider(fake_transport({"water bottle": [dup, dup]})).search(
            ["water bottle"], marketplace="US"
        )
        assert len(of_kind(found, "catalog_item")) == 1
        assert of_kind(found, "catalog_search")[0].payload["result_asins"] == ("B0MKTW0001",)

    def test_duplicate_queries_are_called_once(self):
        transport = fake_transport(BOOK)
        provider(transport).search(["cozy mystery", " Cozy  Mystery "], marketplace="US")
        assert len(transport.requests) == 1

    def test_partial_failure_keeps_the_other_queries(self):
        transport = fake_transport(
            BOOK,
            overrides={
                "cozy mystery": failure(
                    429, {"errors": [{"code": "QuotaExceeded", "message": "slow down"}]}
                )
            },
        )
        p = provider(transport)
        found = p.search(["cozy mystery", "small town mystery"], marketplace="US", run_id="r")
        assert [e.subject for e in of_kind(found, "catalog_search")] == ["small town mystery"]
        assert ("cozy mystery", "http_429 QuotaExceeded") in p.failures

    def test_missing_fields_and_empty_results(self):
        bare = {"asin": "B0MKTW0005", "summaries": [{"marketplaceId": US, "itemName": "Bare"}]}
        no_summary = {"asin": "B0MKTW0006"}
        bad_asin = {"asin": "x", "summaries": [{"marketplaceId": US, "itemName": "Bad"}]}
        p = provider(fake_transport({"water bottle": [bare, no_summary, bad_asin], "empty": []}))
        found = p.search(["water bottle", "empty"], marketplace="US")
        (item,) = of_kind(found, "catalog_item")
        assert item.payload["bullets"] == () and "brand" not in item.payload
        searches = of_kind(found, "catalog_search")
        assert searches[1].payload["result_asins"] == ()  # an empty result is still evidence
        assert sum(1 for _, r in p.failures if r.startswith("item skipped")) == 2

    @pytest.mark.parametrize(
        "response, reason",
        [
            (failure(200, ["not", "an", "object"]), "malformed"),
            (failure(200, {"numberOfResults": 0}), "malformed"),
            (failure(200, {"items": "nope"}), "malformed"),
            (failure(200, None, text="<html>oops</html>"), "malformed"),
            (failure(500, None, text="Internal error"), "http_500"),
            (failure(403, {"errors": [{"code": "Unauthorized"}]}), "http_403 Unauthorized"),
        ],
    )
    def test_malformed_and_error_responses_produce_no_evidence(self, response, reason):
        p = provider(fake_transport({}, overrides={"water bottle": response}))
        assert p.search(["water bottle"], marketplace="US") == []
        assert p.failures[0][1].startswith(reason)

    def test_transport_errors_are_recorded_failures(self, tmp_path):
        replay_path = tmp_path / "empty.jsonl"
        provider(RecordingHttpTransport(fake_transport(BOOK), replay_path)).search(
            ["small town mystery"], marketplace="US"
        )
        p = provider(ReplayHttpTransport(replay_path))
        assert p.search(["cozy mystery"], marketplace="US") == []
        assert p.failures == [("cozy mystery", "replay_miss")]


# -- call budget and plan ------------------------------------------------------------------


class TestCallLimit:
    def test_hard_cap_halts_remaining_calls(self):
        transport = fake_transport(BOOK)
        p = provider(transport, max_calls_per_run=1)
        found = p.search(["cozy mystery", "small town mystery"], marketplace="US", run_id="r")
        assert len(transport.requests) == 1
        assert [e.subject for e in of_kind(found, "catalog_search")] == ["cozy mystery"]
        assert ("small town mystery", "call_limit") in p.failures
        assert p.halts == ["max_calls_per_run=1 reached"]
        assert p.calls_made("r") == 1

    def test_cap_counts_every_call_in_a_run(self):
        transport = fake_transport(BOOK)
        p = provider(transport, max_calls_per_run=2)
        p.search(["cozy mystery"], marketplace="US", run_id="r")
        p.get_items(["B0MKTB0001"], marketplace="US", run_id="r")
        p.search(["small town mystery"], marketplace="US", run_id="r")
        assert len(transport.requests) == 2

    def test_zero_cap_makes_no_calls(self):
        transport = fake_transport(BOOK)
        assert provider(transport, max_calls_per_run=0).search(["x"], marketplace="US") == []
        assert transport.requests == []

    def test_replay_is_not_counted_against_the_live_budget(self, tmp_path):
        path = tmp_path / "rec.jsonl"
        provider(RecordingHttpTransport(fake_transport(BOOK), path)).search(
            ["cozy mystery", "small town mystery"], marketplace="US"
        )
        p = provider(ReplayHttpTransport(path), max_calls_per_run=0)
        assert len(of_kind(p.search(["cozy mystery"], marketplace="US"), "catalog_search")) == 1

    def test_query_limit_skips_explicitly(self):
        transport = fake_transport(BOOK)
        p = provider(transport, query_limit=1)
        p.search(["cozy mystery", "small town mystery"], marketplace="US")
        assert len(transport.requests) == 1
        assert ("small town mystery", "skipped: query_limit=1") in p.failures

    def test_plan(self):
        p = provider(fake_transport(BOOK), max_calls_per_run=4)
        plan = p.plan(marketplace="US", keywords=["cozy mystery", "small town mystery"])
        assert (plan.calls, plan.call_cap, plan.within_cap) == (2, 4, True)
        assert plan.expected_cost_usd == 0.0 and plan.worst_case_cost_usd == 0.0
        text = render_market_plan(plan)
        assert "2 network calls (cap 4, within cap)" in text
        assert "rate limit 5 req/s" in text and "'small town mystery'" in text
        over = provider(fake_transport(BOOK), max_calls_per_run=1).plan(
            marketplace="US", keywords=["a", "b"], asins=["B0MKTB0001"]
        )
        assert (over.calls, over.within_cap) == (3, False)

    def test_bad_settings(self):
        with pytest.raises(ValueError):
            provider(fake_transport(BOOK), page_size=21)
        with pytest.raises(ValueError):
            provider(fake_transport(BOOK), max_calls_per_run=-1)


# -- marketplace scoping -------------------------------------------------------------------


class TestMarketplace:
    def test_other_marketplace_items_are_not_evidence(self):
        p = provider(fake_transport(BOOK))
        found = p.search(["small town mystery"], marketplace="US")
        assert "B0MKTB0099" not in {e.subject for e in found}
        assert "B0MKTB0099" not in of_kind(found, "catalog_search")[0].payload["result_asins"]

    def test_bullets_from_other_marketplaces_are_dropped(self):
        item = sp_item("B0MKTW0007", "Bottle", ["US bullet"])
        item["attributes"]["bullet_point"].append(
            {"value": "UK bullet", "marketplace_id": "A1F83G8C2ARO7P"}
        )
        found = provider(fake_transport({"bottle": [item]})).search(["bottle"], marketplace="US")
        assert of_kind(found, "catalog_item")[0].payload["bullets"] == ("US bullet",)

    def test_marketplace_maps_to_id_and_regional_endpoint(self):
        transport = fake_transport({})
        provider(transport).search(["bottle"], marketplace="UK")
        request = transport.requests[0]
        assert request.base_url == "https://sellingpartnerapi-eu.amazon.com"
        assert params(request)["marketplaceIds"] == "A1F83G8C2ARO7P"

    def test_unknown_marketplace_is_refused(self):
        with pytest.raises(UnsupportedMarketplace):
            provider(fake_transport({})).search(["bottle"], marketplace="ZZ")


# -- record / replay -------------------------------------------------------------------------


class TestRecordReplay:
    def test_replay_reproduces_exact_evidence_and_downstream_outputs(self, tmp_path):
        for name in NAMES:
            path = tmp_path / f"{name}.jsonl"
            recorded, _ = run(name, provider(RecordingHttpTransport(fake_transport(name), path)))
            replayed, _ = run(name, provider(ReplayHttpTransport(path)))
            assert replayed.evidence.ids_by_kind == recorded.evidence.ids_by_kind
            assert replayed.metadata.evidence_fingerprint == recorded.metadata.evidence_fingerprint
            assert replayed.ranked == recorded.ranked
            assert replayed.recommendations == recorded.recommendations
            assert replayed.proposals == recorded.proposals
            assert replayed.unsupported_opportunities == recorded.unsupported_opportunities

    def test_recording_appends_and_never_rewrites(self, tmp_path):
        path = tmp_path / "rec.jsonl"
        provider(RecordingHttpTransport(fake_transport(BOOK), path)).search(
            ["cozy mystery"], marketplace="US"
        )
        first = path.read_bytes()
        provider(RecordingHttpTransport(fake_transport(BOOK), path)).search(
            ["small town mystery"], marketplace="US"
        )
        assert path.read_bytes().startswith(first)
        assert len(ReplayHttpTransport(path)) == 2

    def test_tampered_recording_is_rejected(self, tmp_path):
        path = tmp_path / "rec.jsonl"
        provider(RecordingHttpTransport(fake_transport(BOOK), path)).search(
            ["cozy mystery"], marketplace="US"
        )
        text = path.read_text(encoding="utf-8").replace("Lighthouse", "Lamphouse")
        path.write_text(text, encoding="utf-8")
        with pytest.raises(Exception, match="checksum"):
            ReplayHttpTransport(path)

    def test_recordings_never_contain_credentials(self, tmp_path, monkeypatch):
        monkeypatch.setenv("SP_API_LWA_CLIENT_ID", "amzn1.application-oa2-client.fakeid")
        monkeypatch.setenv("SP_API_LWA_CLIENT_SECRET", "fakesecret")
        monkeypatch.setenv("SP_API_REFRESH_TOKEN", "Atzr|fakerefresh")
        live = LiveSpApiTransport(allow_live=True, rate_per_second=1000, opener=FakeOpener())
        path = tmp_path / "rec.jsonl"
        provider(RecordingHttpTransport(live, path)).search(["water bottle"], marketplace="US")
        text = path.read_text(encoding="utf-8")
        for secret in ("fakeid", "fakesecret", "fakerefresh", "Atza|fakeaccess"):
            assert secret not in text


# -- live transport, without the network --------------------------------------------------


class FakeResponse:
    def __init__(self, status, body, headers=None):
        self.status, self._body, self.headers = status, body, headers or {}

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeOpener:
    def __init__(self):
        self.requests = []

    def __call__(self, request, timeout):
        self.requests.append(request)
        if request.full_url == "https://api.amazon.com/auth/o2/token":
            body = json.dumps({"access_token": "Atza|fakeaccess", "expires_in": 3600})
            return FakeResponse(200, body.encode())
        body = json.dumps({"numberOfResults": 1, "items": BOTTLE["water bottle"][:1]})
        return FakeResponse(200, body.encode(), {"x-amzn-requestid": "req-1", "x-secret": "no"})


class TestLiveTransport:
    def test_disabled_without_the_flag(self, monkeypatch):
        monkeypatch.delenv("ATLAS_ALLOW_LIVE_MARKET", raising=False)
        with pytest.raises(LiveMarketDisabled):
            provider(LiveSpApiTransport()).search(["water bottle"], marketplace="US")

    def test_missing_credentials_fail_before_any_network(self, monkeypatch):
        for name in ("SP_API_LWA_CLIENT_ID", "SP_API_LWA_CLIENT_SECRET", "SP_API_REFRESH_TOKEN"):
            monkeypatch.delenv(name, raising=False)
        opener = FakeOpener()
        p = provider(LiveSpApiTransport(allow_live=True, opener=opener))
        assert p.search(["water bottle"], marketplace="US") == []
        assert p.failures[0][1] == "transport_error: HttpTransportError"
        assert opener.requests == []
        with pytest.raises(HttpTransportError, match="credentials missing"):
            LiveSpApiTransport(allow_live=True, opener=opener)._access_token()

    def test_lwa_exchange_and_headers(self, monkeypatch):
        monkeypatch.setenv("SP_API_LWA_CLIENT_ID", "cid")
        monkeypatch.setenv("SP_API_LWA_CLIENT_SECRET", "csecret")
        monkeypatch.setenv("SP_API_REFRESH_TOKEN", "rtoken")
        opener = FakeOpener()
        live = LiveSpApiTransport(allow_live=True, rate_per_second=1000, opener=opener)
        p = provider(live)
        found = p.search(["water bottle", "insulated water bottle"], marketplace="US")
        token_calls = [r for r in opener.requests if "auth/o2/token" in r.full_url]
        assert len(token_calls) == 1  # the access token is cached for the hour
        api = [r for r in opener.requests if "auth/o2/token" not in r.full_url]
        assert len(api) == 2
        assert api[0].get_header("X-amz-access-token") == "Atza|fakeaccess"
        assert api[0].get_header("User-agent").startswith("atlas-amazon/")
        assert of_kind(found, "catalog_item")[0].subject == "B0MKTW0001"
        assert p.calls_made(None) == 2


# -- ResearchRun integration ---------------------------------------------------------------


@pytest.fixture(scope="module")
def market_runs():
    out = {}
    for name in NAMES:
        baseline, _ = run(name)
        market_store = InMemoryEvidenceStore()
        market, _ = run(name, provider(fake_transport(name)), market_store)
        out[name] = (baseline, market, market_store)
    return out


class TestResearchIntegration:
    def test_market_items_join_as_competitors_without_duplicates(self, market_runs):
        _, market, store = market_runs["book_cozy_mystery"]
        items = [store.get(i) for i in market.evidence.ids_by_kind["catalog_item"]]
        subjects = [e.subject for e in items]
        assert len(subjects) == len(set(subjects))
        assert "B0BOOK0001" not in subjects  # the product is not its own competitor
        sp = {e.subject for e in items if e.provider == "sp-api-catalog"}
        assert sp == {"B0MKTB0001", "B0MKTB0002", "B0MKTB0003"}
        assert "B0BOOKC001" not in sp  # already fetched as a named competitor
        assert len(market.evidence.ids_by_kind["catalog_search"]) == 2
        assert market.metadata.providers["catalog_search"] == "sp-api-catalog"

    def test_catalog_data_never_becomes_demand(self, market_runs):
        for name in NAMES:
            baseline, market, _ = market_runs[name]
            assert (
                market.evidence.ids_by_kind["keyword_metric"]
                == baseline.evidence.ids_by_kind["keyword_metric"]
            )
            market_candidates = {c.keyword for c in market.candidates}
            for d in market.derivations:
                if d.keyword in market_candidates and d.keyword not in {
                    c.keyword for c in baseline.candidates
                }:
                    assert "search_volume" in d.missing or d.signals is None

    def test_market_opportunity_visible_unsupported_claims_blocked(self, market_runs):
        baseline, market, store = market_runs["physical_water_bottle"]
        c = compare_market(baseline, market, store, provider="sp-api-catalog")
        tempting = {t.keyword: t for t in c.tempting_unsupported}
        assert "bpa free" in tempting and tempting["bpa free"].market_items >= 3
        for t in tempting.values():
            assert not t.recommended and not t.packed
        recs = {r.keyword for r in market.recommendations}
        packed = set(market.backend_plan.packed_keywords)
        assert not set(tempting) & (recs | packed)
        proposal = " ".join(str(p.value) for p in market.proposals).split()
        assert "bpa" not in proposal and "straw" not in proposal

    def test_comparison_reports_new_confirmed_and_absent(self, market_runs):
        baseline, market, store = market_runs["book_cozy_mystery"]
        c = compare_market(baseline, market, store, provider="sp-api-catalog")
        assert c.queries == ("cozy mystery", "small town mystery")
        assert set(c.market_items) == {"B0MKTB0001", "B0MKTB0002", "B0MKTB0003"}
        assert {p.keyword for p in c.confirmed} >= {"cozy mystery", "small town"}
        assert set(c.absent) | {p.keyword for p in c.confirmed} == {
            k.keyword for k in baseline.candidates
        }
        assert set(c.new_without_demand) <= set(c.new_candidates)
        text = "\n".join(render_market_comparison("book_cozy_mystery", c))
        assert "Market queries (sp-api-catalog)" in text

    def test_plan_only_skips_live_market_calls(self):
        transport = fake_transport("book_cozy_mystery")
        sc = load_scenario(SCENARIOS / "book_cozy_mystery.json").with_providers(
            catalog_search=provider(transport)
        )
        from atlas_amazon.research import ResearchRun

        research = ResearchRun(
            product=sc.product,
            listing=sc.listing,
            recipe_id=sc.product.recipe_id,
            run_id=sc.run_id,
            providers=sc.providers,
            store=InMemoryEvidenceStore(),
            started_at=sc.started_at,
        )
        research.plan_semantics()
        assert transport.requests == []

    def test_without_market_provider_nothing_changes(self, market_runs):
        for name in NAMES:
            baseline, _, _ = market_runs[name]
            assert "catalog_search" not in baseline.evidence.ids_by_kind
            assert "catalog_search" not in baseline.metadata.providers


# -- live runner, without the network ---------------------------------------------------------


def load_runner():
    import importlib.util

    from test_examples import ROOT

    spec = importlib.util.spec_from_file_location(
        "record_live_market", ROOT / "scripts" / "record_live_market.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestLiveRunner:
    def test_plan_matches_the_cap(self):
        runner = load_runner()
        plans = runner.plans()
        assert {n: p.calls for n, p in plans.items()} == {
            "book_cozy_mystery": 2,
            "physical_water_bottle": 2,
        }
        assert all(p.within_cap and p.worst_case_cost_usd == 0 for p in plans.values())

    def test_run_refuses_without_access_and_writes_nothing(self, tmp_path, monkeypatch):
        runner = load_runner()
        monkeypatch.setattr(runner, "LIVE", tmp_path)
        monkeypatch.delenv("ATLAS_ALLOW_LIVE_MARKET", raising=False)
        monkeypatch.setattr("sys.argv", ["x", "--run", "--dir", "fresh"])
        assert runner.main() == 4
        assert not (tmp_path / "fresh").exists()
        monkeypatch.setenv("ATLAS_ALLOW_LIVE_MARKET", "1")
        for name in ("SP_API_LWA_CLIENT_ID", "SP_API_LWA_CLIENT_SECRET", "SP_API_REFRESH_TOKEN"):
            monkeypatch.delenv(name, raising=False)
        assert runner.preflight().startswith("missing credentials")

    def test_run_refuses_to_reuse_a_recordings_directory(self, tmp_path, monkeypatch):
        runner = load_runner()
        monkeypatch.setattr(runner, "LIVE", tmp_path)
        (tmp_path / "used").mkdir()
        (tmp_path / "used" / "book_cozy_mystery.jsonl").write_text("{}\n", encoding="utf-8")
        monkeypatch.setattr("sys.argv", ["x", "--run", "--dir", "used"])
        assert runner.main() == 3
        assert (tmp_path / "used" / "book_cozy_mystery.jsonl").read_text() == "{}\n"


# -- synthetic demonstration report -------------------------------------------------------


def test_synthetic_market_report_is_current(market_runs):
    from atlas_amazon.research.market import render_market_report
    from test_examples import ROOT, check

    header = [
        "> **SYNTHETIC, not live.** Fake SP-API `searchCatalogItems` responses "
        "(`tests/market_helpers.py`, ASINs `B0MKT…`) fed through the real adapter and research "
        "run, to show what the live comparison reports. No network calls were made. Catalog "
        "evidence only: no search volume, conversion or ad data.",
    ]
    comparisons = {
        name: compare_market(baseline, market, store, provider="sp-api-catalog")
        for name, (baseline, market, store) in market_runs.items()
    }
    check(
        ROOT / "docs" / "baselines" / "market_v0.10_synthetic.md",
        render_market_report("Market data comparison (v0.10, synthetic)", header, comparisons),
    )
