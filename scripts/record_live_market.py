"""Record the v0.10 live market-data slice (SP-API searchCatalogItems). Read-only; opt-in.

Per example scenario, one catalog keyword search per seed keyword (first page,
pageSize 10), recorded to tests/fixtures/recordings/live/market_v10/<scenario>.jsonl
and fed to the research run as competitor evidence (`catalog_search` role).
Semantic judgments stay the scenario's fixture judgments: no LLM calls.

Hard limits:
* MAX_CALLS_PER_SCENARIO catalog calls per scenario, enforced by the provider
  before every call (the API has no per-call fee, so call volume is the budget);
* the recordings directory must not exist or be empty: earlier recordings are
  never overwritten or appended to;
* an authorization failure (HTTP 401/403) stops the run before the next scenario.

Credentials come only from the environment: SP_API_LWA_CLIENT_ID,
SP_API_LWA_CLIENT_SECRET, SP_API_REFRESH_TOKEN (a Selling Partner API app
authorized for a seller account with catalog access). Live calls also need
ATLAS_ALLOW_LIVE_MARKET=1. Credentials and access tokens are never printed,
stored or recorded.

    python scripts/record_live_market.py --plan    # print the plan and cap; no calls
    python scripts/record_live_market.py --check   # credentials + LWA token exchange only
    python scripts/record_live_market.py --run     # check, plan, record live, write report
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from atlas_amazon.evidence import InMemoryEvidenceStore
from atlas_amazon.providers.sp_api import (
    LIVE_MARKET_FLAG,
    LiveSpApiTransport,
    RecordingHttpTransport,
    SpApiCatalogProvider,
    render_market_plan,
)
from atlas_amazon.providers.sp_api.http import CREDENTIAL_ENV, HttpTransportError
from atlas_amazon.research import load_scenario
from atlas_amazon.research.market import compare_market, render_market_report

ROOT = Path(__file__).resolve().parent.parent
SCENARIOS = ROOT / "tests" / "fixtures" / "scenarios"
LIVE = ROOT / "tests" / "fixtures" / "recordings" / "live"
REPORT = ROOT / "docs" / "baselines" / "live_market_v0.10.md"
NAMES = ("book_cozy_mystery", "physical_water_bottle")
MAX_CALLS_PER_SCENARIO = 2
PAGE_SIZE = 10


def market_provider(transport) -> SpApiCatalogProvider:
    return SpApiCatalogProvider(
        transport, max_calls_per_run=MAX_CALLS_PER_SCENARIO, page_size=PAGE_SIZE
    )


def plans():
    out = {}
    for name in NAMES:
        sc = load_scenario(SCENARIOS / f"{name}.json")
        seeds = sc.product.attributes["seed_keywords"]
        out[name] = market_provider(LiveSpApiTransport(allow_live=False)).plan(
            marketplace=sc.product.marketplace, keywords=seeds
        )
    return out


def print_plans(out_dir: Path) -> int:
    total = 0
    for name, plan in plans().items():
        print(f"## {name}\n{render_market_plan(plan)}\n")
        total += plan.calls
    print(
        f"TOTAL catalog calls {total} (cap {MAX_CALLS_PER_SCENARIO} per scenario, "
        f"{MAX_CALLS_PER_SCENARIO * len(NAMES)} total) + 1 LWA token exchange; cost $0.00 "
        f"(no per-call fee); rate limit 5 req/s."
    )
    print(f"recordings directory: {out_dir} ({'fresh' if fresh(out_dir) else 'NOT fresh'})")
    return total


def fresh(out_dir: Path) -> bool:
    return not out_dir.exists() or not any(out_dir.iterdir())


def preflight() -> str | None:
    """None when credentials work for an LWA token exchange; otherwise the problem."""
    if os.environ.get(LIVE_MARKET_FLAG) != "1":
        return f"{LIVE_MARKET_FLAG}=1 is not set"
    missing = [n for n in CREDENTIAL_ENV if not os.environ.get(n)]
    if missing:
        return f"missing credentials: {', '.join(missing)}"
    try:
        LiveSpApiTransport(allow_live=True)._access_token()
    except (HttpTransportError, OSError, KeyError, ValueError) as exc:
        return f"LWA token exchange failed: {type(exc).__name__}"
    return None


def record(out_dir: Path) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    live = LiveSpApiTransport()
    comparisons, calls = {}, 0
    for name in NAMES:
        sc = load_scenario(SCENARIOS / f"{name}.json")
        baseline = sc.run()
        provider = market_provider(RecordingHttpTransport(live, out_dir / f"{name}.jsonl"))
        store = InMemoryEvidenceStore()
        market = sc.with_providers(catalog_search=provider).run(store=store)
        calls += provider.calls_made(sc.run_id)
        for label, reason in provider.failures:
            print(f"{name}: {label!r}: {reason}")
        comparisons[name] = compare_market(baseline, market, store, provider=provider.name)
        if any(r.startswith(("http_401", "http_403")) for _, r in provider.failures):
            print("authorization failed; stopping before the next scenario")
            break
    header = [
        "> **Live, read-only.** SP-API `searchCatalogItems` (2022-04-01), US marketplace, one "
        f"first-page keyword search per seed (pageSize {PAGE_SIZE}). {calls} catalog calls, "
        "$0.00. Recordings: `tests/fixtures/recordings/live/market_v10/`. Catalog evidence "
        "only: no search volume, conversion or ad data; catalog order is not search rank.",
    ]
    REPORT.write_text(
        render_market_report("Live market data (v0.10)", header, comparisons),
        encoding="utf-8",
        newline="\n",
    )
    print(f"live catalog calls: {calls}; report: {REPORT}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--plan", action="store_true")
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--run", action="store_true")
    parser.add_argument("--dir", default="market_v10", help="recordings subdirectory under live/")
    args = parser.parse_args()
    out_dir = LIVE / args.dir
    if args.check:
        problem = preflight()
        print("SP-API check: " + ("OK" if problem is None else f"FAILED: {problem}"))
        return 0 if problem is None else 4
    print_plans(out_dir)
    if args.plan:
        return 0
    if not fresh(out_dir):
        print(f"{out_dir} already has recordings; refusing to overwrite or append")
        return 3
    problem = preflight()
    if problem is not None:
        print(f"SP-API check FAILED: {problem}; no calls made, nothing recorded")
        return 4
    return record(out_dir)


if __name__ == "__main__":
    sys.exit(main())
