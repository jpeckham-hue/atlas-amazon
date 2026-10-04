"""Old vs new semantic architecture, per scenario, offline.

Compares, for one scenario:

* **v0.4b** (one call per judgment, Claude Opus 5.5, 4,096 output tokens per
  call): from the committed v0.4b recording, priced with
  `estimate_recording_cost`. Those are the exact request bodies v0.4b sent.
* **v0.5** (human -> rules -> cache -> batched fast tier -> selective
  escalation): from the committed v0.5 recording, priced the same way at the
  model each request named, and from the run's call plans (which add the
  escalation reserve to the worst case).
* **Downstream equivalence**: the same scenario run with individual calls
  (`LLMJudgmentProvider`, no rules, no skipping) and with the batched
  provider, both answered by the same scripted responder. Ranking, entity
  flags and proposals must match.

Everything here is an estimate from synthetic recordings (token counts from
text size, list prices). No figure is a measured cost and nothing here says
anything about real model quality.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from atlas_amazon.providers.fixtures import FixtureData
from atlas_amazon.research.run import ResearchConfig, ResearchResult
from atlas_amazon.research.scenarios import load_scenario
from atlas_amazon.semantic.batched import BatchedJudgmentProvider
from atlas_amazon.semantic.llm import LLMJudgmentProvider, LLMReviewThemeProvider
from atlas_amazon.semantic.plan import RunSemanticPlan
from atlas_amazon.semantic.synthetic import fixture_responder
from atlas_amazon.semantic.transport import ReplayTransport, ScriptedTransport
from atlas_amazon.semantic.usage import CostEstimate, UsageLedger, estimate_recording_cost

V04B_MODEL = "claude-opus-5-5"


@dataclass(frozen=True, slots=True)
class ScenarioBenchmark:
    name: str
    old: CostEstimate  # v0.4b recording, Opus 5.5
    new: CostEstimate  # v0.5 recording, priced per requested model
    plan: RunSemanticPlan  # v0.5 call plans from the replayed run
    judgments_requested: int
    human: int
    deterministic: int
    skipped: int
    model_judgments: int
    escalations: int
    downstream_identical: bool
    differences: tuple[str, ...]


def _downstream(result: ResearchResult) -> dict:
    return {
        "ranking": [(s.keyword, round(s.score, 9)) for s in result.ranked],
        "entity_flags": sorted((f.keyword, f.label) for f in result.entity_flags),
        "proposals": [str(p.value) for p in result.proposals],
        "recommendations": [(r.kind.value, r.keyword) for r in result.recommendations],
        "families": [f.phrases for f in result.families.families],
    }


def compare_downstream(scenario_path: Path) -> tuple[bool, tuple[str, ...]]:
    """Individual vs batched execution against the same scripted answers."""
    raw = json.loads(Path(scenario_path).read_text(encoding="utf-8"))
    fixture = FixtureData.from_dict(raw["fixture"])
    scenario = load_scenario(scenario_path)

    def run(provider_cls, config: ResearchConfig) -> ResearchResult:
        transport = ScriptedTransport(fixture_responder(fixture))
        ledger = UsageLedger()
        return scenario.with_providers(
            judgments=provider_cls(transport, ledger=ledger),
            review_themes=LLMReviewThemeProvider(transport, ledger=ledger),
        ).run(config=config)

    individual = _downstream(
        run(
            LLMJudgmentProvider,
            ResearchConfig(deterministic_judgments=False, skip_unrankable_judgments=False),
        )
    )
    batched = _downstream(run(BatchedJudgmentProvider, ResearchConfig()))
    diffs = tuple(k for k in individual if individual[k] != batched[k])
    return not diffs, diffs


def benchmark_scenario(
    name: str, *, scenarios: Path, recordings: Path, v04b_recordings: Path
) -> ScenarioBenchmark:
    scenario_path = scenarios / f"{name}.json"
    recording = recordings / f"{name}.jsonl"
    transport = ReplayTransport(recording)
    ledger = UsageLedger()
    result = (
        load_scenario(scenario_path)
        .with_providers(
            judgments=BatchedJudgmentProvider(transport, ledger=ledger),
            review_themes=LLMReviewThemeProvider(transport, ledger=ledger),
        )
        .run()
    )
    usage = result.semantic_usage
    assert usage is not None
    plan = RunSemanticPlan(result.metadata.run_id, result.semantic_plans)
    judgment_stages = [p for p in plan.stages if p.stage != "review_themes"]
    identical, diffs = compare_downstream(scenario_path)
    return ScenarioBenchmark(
        name=name,
        old=estimate_recording_cost(v04b_recordings / f"{name}.jsonl", V04B_MODEL),
        new=estimate_recording_cost(recording),
        plan=plan,
        judgments_requested=sum(p.requested for p in judgment_stages),
        human=usage.human_overrides,
        deterministic=usage.deterministic_judgments,
        skipped=usage.skipped_judgments,
        model_judgments=usage.model_judgments,
        escalations=usage.escalations,
        downstream_identical=identical,
        differences=diffs,
    )


def _m(value: float | None) -> str:
    return "unknown" if value is None else f"${value:.4f}"


def render_benchmark_markdown(rows: list[ScenarioBenchmark]) -> str:
    lines = [
        "# Semantic cost benchmark: v0.4b vs v0.5",
        "",
        "> **Estimates from synthetic recordings.** Token counts are approximated from "
        "text size (4 chars per token) and priced at list prices "
        f"(pricing as of {rows[0].plan.stages[0].pricing_as_of if rows else '-'}). "
        "No live model was called: nothing here is a measured cost or a statement "
        "about model quality. v0.4b expected costs exclude Opus 5.5's always-on "
        "thinking tokens, so they understate v0.4b.",
        "",
        "Regenerate with `ATLAS_REGEN_EXAMPLES=1 pytest tests/test_benchmark.py`.",
        "",
        "## API calls",
        "",
        "| Scenario | v0.4b calls | v0.5 calls (recorded) | v0.5 planned / expected / worst |",
        "|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r.name} | {r.old.calls} | {r.new.calls} | {r.plan.planned_calls} / "
            f"{r.plan.expected_calls} / {r.plan.worst_case_calls} |"
        )
    lines += [
        "",
        "## Cost per run",
        "",
        "| Scenario | v0.4b expected | v0.5 expected (recorded) | v0.5 expected (plan) "
        "| v0.4b worst case | v0.5 worst case (recorded) | v0.5 worst case (plan) |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r.name} | {_m(r.old.estimated_cost_usd)} | {_m(r.new.estimated_cost_usd)} | "
            f"{_m(r.plan.expected_cost_usd)} | {_m(r.old.worst_case_cost_usd)} | "
            f"{_m(r.new.worst_case_cost_usd)} | {_m(r.plan.worst_case_cost_usd)} |"
        )
    lines += [
        "",
        "The plan's worst case includes the escalation reserve (strong-tier calls the "
        "policy could add up to its cap); the recorded worst case prices only the calls "
        "that were made, each at its full `max_tokens`.",
        "",
        "## Cost per judgment",
        "",
        "| Scenario | Judgments | v0.4b expected / judgment | v0.5 expected / judgment (plan) |",
        "|---|---|---|---|",
    ]
    for r in rows:
        old_per = r.old.estimated_cost_usd / r.judgments_requested
        plan_cost = r.plan.expected_cost_usd
        new_per = None if plan_cost is None else plan_cost / r.judgments_requested
        lines.append(f"| {r.name} | {r.judgments_requested} | {_m(old_per)} | {_m(new_per)} |")
    lines += [
        "",
        "## Semantic judgments",
        "",
        "| Scenario | Requested (v0.4b and v0.5) | Human | Deterministic | Not needed "
        "| Model | Escalated | Downstream identical |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        same = "yes" if r.downstream_identical else f"no: {', '.join(r.differences)}"
        lines.append(
            f"| {r.name} | {r.judgments_requested} | {r.human} | {r.deterministic} | "
            f"{r.skipped} | {r.model_judgments} | {r.escalations} | {same} |"
        )
    lines += [
        "",
        "Requested judgments are the same in both versions. v0.4b sent every one of them "
        "(plus one review-theme call) to the model, one call each. v0.5 answers human "
        "decisions and deterministic questions without a model, skips relevance and "
        "intent for families that cannot be ranked, and batches the rest. "
        '"Downstream identical" compares ranking, entity flags, proposals, '
        "recommendations and families between individual and batched execution against "
        "the same scripted answers.",
        "",
    ]
    return "\n".join(lines)
