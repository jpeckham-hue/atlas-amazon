"""Record the v0.6 live semantic baseline. Spends real money; opt-in only.

Runs the v0.5 pipeline (BatchedJudgmentProvider + LLMReviewThemeProvider, the
default fast/strong tiers) once per example scenario against the live API,
recording every exchange to tests/fixtures/recordings/live/<scenario>.jsonl
so it can be replayed offline forever after.

Hard limits, enforced before every call by the usage ledger:
* at most MAX_CALLS live API calls per scenario;
* at most TOTAL_CAP_USD across both scenarios: the second scenario's cost
  limit is whatever the first one left (worst case of the next call
  included, so the cap is never crossed).

Live calls go through Vercel AI Gateway (the default live transport). The
credential is AI_GATEWAY_API_KEY (or VERCEL_OIDC_TOKEN) from the
environment; it is passed to the SDK client and to the no-cost preflight
request, never printed or stored. ANTHROPIC_API_KEY is not used. Live calls
also need ATLAS_ALLOW_LIVE_LLM=1.

    python scripts/record_live_baseline.py --plan    # show the plan; no calls
    python scripts/record_live_baseline.py --check   # no-cost gateway auth/model check
    python scripts/record_live_baseline.py --run     # check, plan, then record live
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

from atlas_amazon.evidence import InMemoryEvidenceStore
from atlas_amazon.research import ResearchRun, load_scenario
from atlas_amazon.semantic import (
    BatchedJudgmentProvider,
    LLMReviewThemeProvider,
    RecordingTransport,
    RunSemanticPlan,
    SemanticBudget,
    UsageLedger,
    default_live_transport,
    render_plan_markdown,
)
from atlas_amazon.semantic.records import ChecksummedJsonl
from atlas_amazon.semantic.tiers import ModelTiers
from atlas_amazon.semantic.transport import GATEWAY_BASE_URL, GATEWAY_KEY_ENV

ROOT = Path(__file__).resolve().parent.parent
SCENARIOS = ROOT / "tests" / "fixtures" / "scenarios"
OUT = ROOT / "tests" / "fixtures" / "recordings" / "live"
NAMES = ("book_cozy_mystery", "physical_water_bottle")
MAX_CALLS = 10
TOTAL_CAP_USD = 0.25


def build_run(name: str, transport, ledger: UsageLedger) -> ResearchRun:
    sc = load_scenario(SCENARIOS / f"{name}.json").with_providers(
        judgments=BatchedJudgmentProvider(transport, ledger=ledger),
        review_themes=LLMReviewThemeProvider(transport, ledger=ledger),
    )
    return ResearchRun(
        product=sc.product,
        listing=sc.listing,
        recipe_id=sc.product.recipe_id,
        run_id=sc.run_id,
        providers=sc.providers,
        store=InMemoryEvidenceStore(),
        started_at=sc.started_at,
    )


def plan_all() -> dict[str, RunSemanticPlan]:
    plans = {}
    for name in NAMES:
        # A transport that refuses live calls: planning never sends anything.
        run = build_run(name, default_live_transport(allow_live=False), UsageLedger())
        plans[name] = run.plan_semantics()
    return plans


def print_plans(plans: dict[str, RunSemanticPlan]) -> None:
    for name, plan in plans.items():
        print(f"## {name}\n")
        print(render_plan_markdown(plan))
    expected = sum(p.expected_cost_usd for p in plans.values())
    worst = sum(p.worst_case_cost_usd for p in plans.values())
    print(
        f"TOTAL planned calls {sum(p.planned_calls for p in plans.values())}, "
        f"worst-case calls {sum(p.worst_case_calls for p in plans.values())}, "
        f"expected ${expected:.4f}, worst case ${worst:.4f} "
        f"(caps: {MAX_CALLS} calls per scenario, ${TOTAL_CAP_USD} total)"
    )


def _gateway_get(path: str, key: str | None) -> dict:
    request = urllib.request.Request(f"{GATEWAY_BASE_URL}{path}")
    if key is not None:
        request.add_header("Authorization", f"Bearer {key}")
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def preflight() -> tuple[str | None, dict]:
    """No-cost gateway check: authenticated credit balance, then model availability.

    Returns (problem, info); problem is None when everything is usable. Neither
    request generates tokens.
    """
    key = next((os.environ[n] for n in GATEWAY_KEY_ENV if os.environ.get(n)), None)
    if key is None:
        return f"no gateway credential: set {GATEWAY_KEY_ENV[0]}", {}
    info: dict = {"credential": next(n for n in GATEWAY_KEY_ENV if os.environ.get(n))}
    try:
        credits = _gateway_get("/v1/credits", key)
    except urllib.error.HTTPError as exc:
        return f"gateway credential rejected: HTTP {exc.code}", info
    except urllib.error.URLError as exc:
        return f"cannot reach the gateway: {exc.reason}", info
    info["credits"] = {k: credits[k] for k in ("balance", "total_used") if k in credits}
    catalog = {m["id"]: m for m in _gateway_get("/v1/models", None).get("data", [])}
    tiers = ModelTiers()
    info["models"] = {}
    for tier, settings in (("fast", tiers.fast), ("strong", tiers.strong)):
        model = catalog.get(settings.model)
        if model is None:
            return f"model {settings.model} ({tier}) is not in the gateway catalog", info
        info["models"][tier] = {"id": settings.model, "pricing": model.get("pricing")}
    return None, info


def record() -> int:
    problem, _ = preflight()
    if problem is not None:
        print(f"not running: {problem}", file=sys.stderr)
        return 4
    OUT.mkdir(parents=True, exist_ok=True)
    existing = [n for n in NAMES if (OUT / f"{n}.jsonl").exists()]
    if existing:
        print(f"refusing to overwrite existing live recordings: {existing}", file=sys.stderr)
        return 2
    spent = 0.0
    summary = {}
    for name in NAMES:
        remaining = TOTAL_CAP_USD - spent
        ledger = UsageLedger(
            budget=SemanticBudget(max_live_calls=MAX_CALLS, max_cost_usd=remaining)
        )
        path = OUT / f"{name}.jsonl"
        transport = RecordingTransport(default_live_transport(), path)
        run = build_run(name, transport, ledger)
        result = run.execute()
        usage = result.semantic_usage
        records = ChecksummedJsonl(path).read() if path.exists() else []
        if any(r["response"].get("synthetic") for r in records):
            raise SystemExit(f"{name}: a recorded response is marked synthetic; not a live run")
        cost = usage.estimated_cost_usd
        errors = [
            f"{r.purpose}: {r.outcome} {r.detail}"
            for r in ledger.records
            if r.outcome not in ("ok", "partial")
        ]
        if usage.live_calls and cost is None:
            raise SystemExit(f"{name}: live cost could not be priced; stopping. Errors: {errors}")
        spent += cost or 0.0
        judges = run.providers.judgments
        summary[name] = {
            "live_calls": usage.live_calls,
            "recorded_exchanges": len(records),
            "fast_calls": usage.fast_calls,
            "strong_calls": usage.strong_calls,
            "escalations": usage.escalations,
            "cache_hits": usage.cache_hits,
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "measured_cost_usd": cost,
            "served_models": sorted({r["response"]["model"] for r in records}),
            "halts": list(usage.halts),
            "errors": errors,
            "failures": [list(f) for f in judges.failures]
            + [list(f) for f in run.providers.review_themes.failures],
            "escalation_events": [
                {"subject": e.subject, "type": e.type, "reason": e.reason, "outcome": e.outcome}
                for e in judges.escalation_events
            ],
        }
        print(f"{name}: {json.dumps(summary[name], indent=2)}")
    print(f"TOTAL measured cost ${spent:.4f} (cap ${TOTAL_CAP_USD})")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--plan", action="store_true")
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--run", action="store_true")
    args = parser.parse_args()
    if args.check:
        problem, info = preflight()
        print(json.dumps(info, indent=2))
        print("gateway check: " + ("OK" if problem is None else f"FAILED: {problem}"))
        return 0 if problem is None else 4
    plans = plan_all()
    print_plans(plans)
    if args.plan:
        return 0
    worst = sum(p.worst_case_cost_usd for p in plans.values())
    if worst > TOTAL_CAP_USD:
        print(f"planned worst case ${worst:.4f} exceeds the ${TOTAL_CAP_USD} cap; not running")
        return 3
    return record()


if __name__ == "__main__":
    raise SystemExit(main())
