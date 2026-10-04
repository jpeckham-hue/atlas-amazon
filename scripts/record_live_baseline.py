"""Record the live semantic baseline (v0.7). Spends real money; opt-in only.

Per example scenario, once:
1. the production pipeline (BatchedJudgmentProvider + LLMReviewThemeProvider,
   default fast/strong tiers, risk-signal escalation), recorded to
   tests/fixtures/recordings/live/v07/<scenario>.jsonl;
2. a strong-tier comparison of the same relevance and intent judgments (evaluation mode,
   never fed into the run), recorded to <scenario>.strong_comparison.jsonl.

The v0.6 recordings in tests/fixtures/recordings/live/ are never touched.

Hard limits, enforced before every call by the usage ledger:
* at most MAX_CALLS live API calls per scenario (production + comparison);
* at most TOTAL_CAP_USD across everything: both production runs go first
  (their combined worst case must fit), then the comparisons; every call's
  worst case is checked against what is left, so the cap is never crossed.

Live calls go through Vercel AI Gateway (the default live transport). The
credential is AI_GATEWAY_API_KEY (or VERCEL_OIDC_TOKEN) from the
environment; it is passed to the SDK client and to the no-cost preflight
request, never printed or stored. ANTHROPIC_API_KEY is not used. Live calls
also need ATLAS_ALLOW_LIVE_LLM=1.

    python scripts/record_live_baseline.py --plan    # show the plan; no calls
    python scripts/record_live_baseline.py --check   # no-cost gateway auth/model check
    python scripts/record_live_baseline.py --run     # check, plan, then record live

Options: `--dir NAME` records into tests/fixtures/recordings/live/NAME (default
v07, the v0.7 baseline); `--production-only` skips the strong comparison.
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
from atlas_amazon.judgments import JudgmentType
from atlas_amazon.research import ResearchRun, load_scenario
from atlas_amazon.semantic import (
    BatchedJudgmentProvider,
    LLMReviewThemeProvider,
    RecordingTransport,
    RunSemanticPlan,
    SemanticBudget,
    SemanticCallPlan,
    UsageLedger,
    default_live_transport,
    render_plan_markdown,
)
from atlas_amazon.semantic.comparison import run_strong_comparison
from atlas_amazon.semantic.records import ChecksummedJsonl
from atlas_amazon.semantic.tiers import ModelTiers
from atlas_amazon.semantic.transport import GATEWAY_BASE_URL, GATEWAY_KEY_ENV

ROOT = Path(__file__).resolve().parent.parent
SCENARIOS = ROOT / "tests" / "fixtures" / "scenarios"
LIVE = ROOT / "tests" / "fixtures" / "recordings" / "live"
OUT = LIVE / "v07"  # replaced by --dir
PRODUCTION_ONLY = False  # replaced by --production-only
NAMES = ("book_cozy_mystery", "physical_water_bottle")
MAX_CALLS = 10
# The comparison covers the judgment types v0.7 changes (entity blocking and
# equivalence already agreed 100% in v0.6), keeping the worst case under the cap.
COMPARISON_TYPES = (JudgmentType.RELEVANCE, JudgmentType.INTENT)
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


def comparison_plan(name: str) -> SemanticCallPlan:
    """Strong-tier comparison of the keyword judgments the model would answer."""
    run = build_run(name, default_live_transport(allow_live=False), UsageLedger())
    requests = [r for r in run.model_requests()["keyword_judgments"] if r.type in COMPARISON_TYPES]
    evaluator = BatchedJudgmentProvider(
        default_live_transport(allow_live=False), evaluation="strong_only"
    )
    return evaluator.plan(requests)


def plan_all() -> dict[str, tuple[RunSemanticPlan, SemanticCallPlan]]:
    plans = {}
    for name in NAMES:
        # A transport that refuses live calls: planning never sends anything.
        run = build_run(name, default_live_transport(allow_live=False), UsageLedger())
        comparison = (
            SemanticCallPlan(stage="strong_comparison", provider="none", requested=0)
            if PRODUCTION_ONLY
            else comparison_plan(name)
        )
        plans[name] = (run.plan_semantics(), comparison)
    return plans


def print_plans(plans) -> None:
    rows = []
    for name, (plan, comparison) in plans.items():
        print(f"## {name}: production pipeline\n")
        print(render_plan_markdown(plan))
        print(f"## {name}: strong-tier comparison (evaluation only)\n")
        print(render_plan_markdown([comparison]))
        rows.append(
            (
                name,
                plan.planned_calls + comparison.planned_calls,
                plan.worst_case_calls + comparison.worst_case_calls,
                plan.expected_cost_usd + comparison.expected_cost_usd,
                plan.worst_case_cost_usd + comparison.worst_case_cost_usd,
            )
        )
    for name, calls, worst_calls, expected, worst in rows:
        print(
            f"{name}: planned calls {calls} (worst {worst_calls}), expected ${expected:.4f}, "
            f"worst case ${worst:.4f}"
        )
    print(
        f"TOTAL planned calls {sum(r[1] for r in rows)}, worst-case calls "
        f"{sum(r[2] for r in rows)}, expected ${sum(r[3] for r in rows):.4f}, worst case "
        f"${sum(r[4] for r in rows):.4f} (caps: {MAX_CALLS} calls per scenario, "
        f"${TOTAL_CAP_USD} total)"
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
    existing = [
        p.name
        for n in NAMES
        for p in (OUT / f"{n}.jsonl", OUT / f"{n}.strong_comparison.jsonl")
        if p.exists()
    ]
    if existing:
        print(f"refusing to overwrite existing live recordings: {existing}", file=sys.stderr)
        return 2
    spent = 0.0
    summary: dict = {}
    state: dict = {}

    def spent_by(ledger, run_id):
        cost = ledger.summary(run_id).estimated_cost_usd
        if ledger.summary(run_id).live_calls and cost is None:
            raise SystemExit("live cost could not be priced; stopping")
        return cost or 0.0

    # Phase 1: both production runs (their worst case fits the cap).
    for name in NAMES:
        ledger = UsageLedger(
            budget=SemanticBudget(max_live_calls=MAX_CALLS, max_cost_usd=TOTAL_CAP_USD - spent)
        )
        path = OUT / f"{name}.jsonl"
        run = build_run(name, RecordingTransport(default_live_transport(), path), ledger)
        result = run.execute()
        spent += spent_by(ledger, result.metadata.run_id)
        state[name] = (ledger, run, result)

    # Phase 2: strong comparisons, each call authorized against what is left.
    for name in NAMES:
        ledger, run, result = state[name]
        run_id = result.metadata.run_id
        before = spent_by(ledger, run_id)
        ledger.budget = SemanticBudget(
            max_live_calls=MAX_CALLS, max_cost_usd=before + (TOTAL_CAP_USD - spent)
        )
        compare_path = OUT / f"{name}.strong_comparison.jsonl"
        comparison = None
        if not PRODUCTION_ONLY:
            comparison = run_strong_comparison(
                RecordingTransport(default_live_transport(), compare_path),
                result.judgments,
                marketplace=result.metadata.marketplace,
                run_id=run_id,
                ledger=ledger,
                types=COMPARISON_TYPES,
            )
        spent += spent_by(ledger, run_id) - before

        path = OUT / f"{name}.jsonl"
        records = [
            r for f in (path, compare_path) if f.exists() for r in ChecksummedJsonl(f).read()
        ]
        if any(r["response"].get("synthetic") for r in records):
            raise SystemExit(f"{name}: a recorded response is marked synthetic; not a live run")
        summary_all = ledger.summary(run_id)
        usage = result.semantic_usage
        judges = run.providers.judgments
        summary[name] = {
            "live_calls_total": summary_all.live_calls,
            "production_calls": usage.live_calls,
            "comparison_items": len(comparison.strong) if comparison else 0,
            "recorded_exchanges": len(records),
            "fast_calls": summary_all.fast_calls,
            "strong_calls": summary_all.strong_calls,
            "escalations": usage.escalations,
            "cache_hits": usage.cache_hits,
            "input_tokens": summary_all.input_tokens,
            "output_tokens": summary_all.output_tokens,
            "measured_cost_usd": summary_all.estimated_cost_usd,
            "served_models": sorted({r["response"]["model"] for r in records}),
            "halts": list(summary_all.halts),
            "errors": [
                f"{r.purpose}: {r.outcome} {r.detail}"
                for r in ledger.records
                if r.outcome not in ("ok", "partial")
            ],
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
    parser.add_argument("--dir", default="v07", help="recordings subdirectory under live/")
    parser.add_argument("--production-only", action="store_true")
    args = parser.parse_args()
    global OUT, PRODUCTION_ONLY
    OUT = LIVE / args.dir
    PRODUCTION_ONLY = args.production_only
    if args.check:
        problem, info = preflight()
        print(json.dumps(info, indent=2))
        print("gateway check: " + ("OK" if problem is None else f"FAILED: {problem}"))
        return 0 if problem is None else 4
    plans = plan_all()
    print_plans(plans)
    if args.plan:
        return 0
    # Production must be able to finish even in its worst case; the comparison
    # only runs while the remaining budget covers each call's worst case.
    production_worst = sum(p.worst_case_cost_usd for p, _ in plans.values())
    expected = sum(p.expected_cost_usd + c.expected_cost_usd for p, c in plans.values())
    if production_worst > TOTAL_CAP_USD or expected > TOTAL_CAP_USD:
        print(
            f"production worst case ${production_worst:.4f} or expected total "
            f"${expected:.4f} exceeds the ${TOTAL_CAP_USD} cap; not running"
        )
        return 3
    return record()


if __name__ == "__main__":
    raise SystemExit(main())
