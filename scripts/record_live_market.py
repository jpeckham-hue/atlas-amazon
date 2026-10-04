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
stored or recorded. Setup: docs/sp-api-setup.md.

    python scripts/record_live_market.py --prereqs # which prerequisites are missing; offline
    python scripts/record_live_market.py --plan    # print the plan and cap; no calls
    python scripts/record_live_market.py --check   # prerequisites + LWA token exchange only
    python scripts/record_live_market.py --run     # check, plan, record live, write report

The report (docs/baselines/live_market_v0.10.md) is rebuilt from the
recordings by tests/test_live_market_v10.py, which replays them offline.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from atlas_amazon.evidence import InMemoryEvidenceStore
from atlas_amazon.providers.sp_api import (
    LiveSpApiTransport,
    RecordingHttpTransport,
    SpApiCatalogProvider,
    render_market_plan,
)
from atlas_amazon.providers.sp_api.http import HttpTransportError
from atlas_amazon.providers.sp_api.preflight import (
    market_prerequisites,
    missing_prerequisites,
    render_prerequisites,
)
from atlas_amazon.research import load_scenario
from atlas_amazon.research.market import compare_market, render_market_report

ROOT = Path(__file__).resolve().parent.parent
SCENARIOS = ROOT / "tests" / "fixtures" / "scenarios"
LIVE = ROOT / "tests" / "fixtures" / "recordings" / "live"
REPORT = ROOT / "docs" / "baselines" / "live_market_v0.10.md"
NAMES = ("book_cozy_mystery", "physical_water_bottle")
MAX_CALLS_PER_SCENARIO = 2
PAGE_SIZE = 10
AUTH_FAILURES = ("http_401", "http_403")


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
    """None when prerequisites are set and an LWA token exchange works; otherwise the problem."""
    missing = missing_prerequisites(market_prerequisites())
    if missing:
        return f"missing prerequisites: {', '.join(missing)}"
    try:
        LiveSpApiTransport(allow_live=True)._access_token()
    except HttpTransportError as exc:  # messages carry status and LWA error code only
        return str(exc)
    except OSError as exc:
        return f"LWA token exchange failed: {type(exc).__name__}"
    return None


def run_scenario(name: str, transport):
    """(provider, comparison) for one scenario with market data from `transport`."""
    sc = load_scenario(SCENARIOS / f"{name}.json")
    baseline = sc.run()
    provider = market_provider(transport)
    store = InMemoryEvidenceStore()
    market = sc.with_providers(catalog_search=provider).run(store=store)
    return provider, compare_market(baseline, market, store, provider=provider.name)


def build_report(comparisons, calls: int, failures) -> str:
    """The live market report; `failures` is {scenario: [(query, reason), ...]}."""
    header = [
        "> **Live, read-only.** SP-API `searchCatalogItems` (2022-04-01), US marketplace, one "
        f"first-page keyword search per seed (pageSize {PAGE_SIZE}). {calls} catalog calls, "
        "$0.00. Recordings: `tests/fixtures/recordings/live/market_v10/`. Catalog evidence "
        "only: no search volume, conversion or ad data; catalog order is not search rank.",
        "",
        "Failed requests and skipped items: "
        + (
            "; ".join(
                f"{name} `{label}`: {reason}"
                for name, items in failures.items()
                for label, reason in items
            )
            or "none"
        )
        + ".",
    ]
    return render_market_report("Live market data (v0.10)", header, comparisons)


def record(out_dir: Path) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    live = LiveSpApiTransport()
    comparisons, failures, calls = {}, {}, 0
    for name in NAMES:
        provider, comparisons[name] = run_scenario(
            name, RecordingHttpTransport(live, out_dir / f"{name}.jsonl")
        )
        calls += provider.total_calls
        failures[name] = list(provider.failures)
        for label, reason in provider.failures:
            print(f"{name}: {label!r}: {reason}")
        if any(r.startswith(AUTH_FAILURES) for _, r in provider.failures):
            print("authorization failed; stopping before the next scenario")
            break
    REPORT.write_text(build_report(comparisons, calls, failures), encoding="utf-8", newline="\n")
    print(f"live catalog calls: {calls}; report: {REPORT}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prereqs", action="store_true")
    mode.add_argument("--plan", action="store_true")
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--run", action="store_true")
    parser.add_argument("--dir", default="market_v10", help="recordings subdirectory under live/")
    args = parser.parse_args()
    out_dir = LIVE / args.dir
    if args.prereqs:
        prerequisites = market_prerequisites(recordings_dir=out_dir)
        print("SP-API prerequisites (values are never shown):")
        print(render_prerequisites(prerequisites))
        return 0 if not missing_prerequisites(prerequisites) else 4
    if args.check:
        print(render_prerequisites(market_prerequisites(recordings_dir=out_dir)))
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
