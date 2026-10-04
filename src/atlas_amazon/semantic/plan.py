"""Semantic call plans: what a stage will cost before any live call is made.

A `SemanticCallPlan` is built by `BatchedJudgmentProvider.plan()` (or
`LLMReviewThemeProvider.plan()`) from the requests of one stage, without
touching the transport. `ResearchRun.plan_semantics()` assembles the plans
of a whole run. Execution follows the plan: the planned fast-tier batches are
exactly the requests that are sent (same request hashes).

Counts, in the order requests are removed:

    requested      judgments the stage asked for
    - human        answered by a human reviewer (never sent to a model)
    - deterministic answered by recipe / keyword rules
    - skipped      not needed (for example a family that cannot be ranked)
    - cache_hits   answered from the semantic cache, per judgment
    = live         judgments that need a model call

`batches` are the fast-tier calls. `escalations` are strong-tier calls that
are already certain (a cached fast answer that the policy escalates).
`escalation_reserve` is what the policy *could* add, up to its cap; it only
counts towards the worst case.

Costs use the planned request bodies (input tokens estimated at 4 chars per
token) and list prices:

* expected: typical output per item, plus `expected_rate` of live items
  escalated to the strong tier;
* worst case: every call uses its full `max_tokens`, and the escalation
  reserve is used in full.

None of these figures is a measurement. Measured cost comes only from the
API-reported usage of live calls (`SemanticUsageSummary`).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class PlannedCall:
    tier: str  # "fast" | "strong"
    model: str
    items: int  # judgments in the call (1 for review themes)
    types: Mapping[str, int]  # judgment type -> count
    max_tokens: int
    input_tokens: int  # estimated
    expected_output_tokens: int
    expected_cost_usd: float | None
    worst_case_cost_usd: float | None
    request_hash: str | None = None  # set for calls whose exact request is known
    item_ids: tuple[str, ...] = ()


def _sum(values: Sequence[float | None]) -> float | None:
    return None if any(v is None for v in values) else float(sum(values))  # type: ignore[arg-type]


@dataclass(frozen=True, slots=True)
class SemanticCallPlan:
    stage: str
    provider: str
    requested: int
    human: int = 0
    deterministic: int = 0
    skipped: int = 0
    cache_hits: int = 0
    live: int = 0
    batches: tuple[PlannedCall, ...] = ()
    escalations: tuple[PlannedCall, ...] = ()
    escalation_reserve: tuple[PlannedCall, ...] = ()
    expected_escalation_calls: int = 0
    expected_escalation_cost_usd: float | None = 0.0
    pricing_as_of: str = ""
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def planned_calls(self) -> int:
        """Calls certain to be made if nothing fails: fast batches plus certain escalations."""
        return len(self.batches) + len(self.escalations)

    @property
    def expected_calls(self) -> int:
        return self.planned_calls + self.expected_escalation_calls

    @property
    def worst_case_calls(self) -> int:
        return self.planned_calls + len(self.escalation_reserve)

    @property
    def expected_cost_usd(self) -> float | None:
        base = _sum([c.expected_cost_usd for c in (*self.batches, *self.escalations)])
        return _sum([base, self.expected_escalation_cost_usd])

    @property
    def worst_case_cost_usd(self) -> float | None:
        return _sum(
            [
                c.worst_case_cost_usd
                for c in (*self.batches, *self.escalations, *self.escalation_reserve)
            ]
        )

    @property
    def max_output_tokens(self) -> int:
        return sum(c.max_tokens for c in (*self.batches, *self.escalations))


@dataclass(frozen=True, slots=True)
class RunSemanticPlan:
    """The semantic plans of one research run, inspectable before execution."""

    run_id: str
    stages: tuple[SemanticCallPlan, ...]
    notes: tuple[str, ...] = ()

    @property
    def requested(self) -> int:
        return sum(s.requested for s in self.stages)

    def total(self, name: str) -> int:
        return sum(getattr(s, name) for s in self.stages)

    @property
    def planned_calls(self) -> int:
        return sum(s.planned_calls for s in self.stages)

    @property
    def expected_calls(self) -> int:
        return sum(s.expected_calls for s in self.stages)

    @property
    def worst_case_calls(self) -> int:
        return sum(s.worst_case_calls for s in self.stages)

    @property
    def expected_cost_usd(self) -> float | None:
        return _sum([s.expected_cost_usd for s in self.stages])

    @property
    def worst_case_cost_usd(self) -> float | None:
        return _sum([s.worst_case_cost_usd for s in self.stages])


def _money(value: float | None) -> str:
    return "unknown (unpriced model)" if value is None else f"${value:.4f}"


def render_plan_markdown(plan: RunSemanticPlan | Sequence[SemanticCallPlan]) -> str:
    stages = plan.stages if isinstance(plan, RunSemanticPlan) else tuple(plan)
    run = plan if isinstance(plan, RunSemanticPlan) else RunSemanticPlan("", stages)
    lines = [
        "| Stage | Requested | Human | Rules | Skipped | Cache | Live | Calls (planned / "
        "expected / worst) | Expected cost | Worst-case cost |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for s in stages:
        lines.append(
            f"| {s.stage} | {s.requested} | {s.human} | {s.deterministic} | {s.skipped} | "
            f"{s.cache_hits} | {s.live} | {s.planned_calls} / {s.expected_calls} / "
            f"{s.worst_case_calls} | {_money(s.expected_cost_usd)} | "
            f"{_money(s.worst_case_cost_usd)} |"
        )
    lines.append(
        f"| **total** | {run.requested} | {run.total('human')} | {run.total('deterministic')} | "
        f"{run.total('skipped')} | {run.total('cache_hits')} | {run.total('live')} | "
        f"{run.planned_calls} / {run.expected_calls} / {run.worst_case_calls} | "
        f"{_money(run.expected_cost_usd)} | {_money(run.worst_case_cost_usd)} |"
    )
    lines.append("")
    calls = [
        (s.stage, kind, c)
        for s in stages
        for kind, group in (
            ("batch", s.batches),
            ("escalation", s.escalations),
            ("reserve", s.escalation_reserve),
        )
        for c in group
    ]
    if calls:
        lines += [
            "| Stage | Call | Tier / model | Items | Types | max_tokens | Est. input tok "
            "| Expected | Worst case |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
        for stage, kind, c in calls:
            types = ", ".join(f"{k} {n}" for k, n in sorted(c.types.items()))
            lines.append(
                f"| {stage} | {kind} | {c.tier} / {c.model} | {c.items} | {types} | "
                f"{c.max_tokens} | {c.input_tokens} | {_money(c.expected_cost_usd)} | "
                f"{_money(c.worst_case_cost_usd)} |"
            )
        lines.append("")
    for s in stages:
        for note in s.notes:
            lines.append(f"- {s.stage}: {note}")
    for note in run.notes:
        lines.append(f"- {note}")
    return "\n".join(lines).rstrip() + "\n"
