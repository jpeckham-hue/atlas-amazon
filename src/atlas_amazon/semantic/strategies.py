"""Offline routing-strategy comparison from recorded answers (v0.8).

Before spending on a new routing strategy, simulate it from answers already
recorded: fast-tier answers from a production recording, strong-tier answers
from a strong comparison (and production escalations). A strategy decides,
per judgment, whether the fast answer stands or the strong answer is used:

* **risk escalation** (`strong_types=()`): the fast answer stands unless the
  escalation policy flags it; then the recorded strong answer replaces it.
* **strong for some types** (e.g. `strong_types={RELEVANCE}`): those types use
  the strong answer outright; the rest follow risk escalation.

A flagged or strong-routed judgment with no recorded strong answer keeps its
fast answer and is listed in `missing_strong` (the simulation never invents
an answer). Recorded strong answers came from a batch with different
neighbours than a live escalation would have, so the simulation is an
approximation of what a live run would return; it is labeled as such
wherever it is reported.

`PrecomputedJudgmentProvider` serves a strategy's final judgments to a real
`ResearchRun`, so downstream effects (ranking, recommendations, proposals)
come from the actual pipeline, not from a re-implementation.

`strategy_cost` prices a strategy with the call planner: planned batches
(fast, and strong for `strong_types`), the escalation calls the simulation
needed, and the planner's worst case (escalation reserve included).
"""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, field

from atlas_amazon.jsonvalue import thaw
from atlas_amazon.judgments.contract import Judgment, JudgmentRequest, JudgmentType
from atlas_amazon.models import Evidence
from atlas_amazon.semantic import batch as b
from atlas_amazon.semantic.batch import batch_items
from atlas_amazon.semantic.batched import BatchedJudgmentProvider
from atlas_amazon.semantic.escalation import EscalationPolicy
from atlas_amazon.semantic.tiers import ModelTier, ModelTiers
from atlas_amazon.semantic.transport import ScriptedTransport


def _key(j: Judgment) -> tuple[str, str]:
    return (j.type.value, j.input_hash)


def _structured(j: Judgment) -> dict:
    return {**thaw(j.result), "confidence": j.confidence, "rationale": j.rationale}


@dataclass(frozen=True, slots=True)
class StrategyOutcome:
    name: str
    judgments: tuple[Judgment, ...]  # one final judgment per fast-tier request
    escalated: tuple[tuple[str, str, str], ...]  # (type, subject, reason)
    strong_routed: tuple[tuple[str, str], ...]  # (type, subject) sent to strong by type
    missing_strong: tuple[tuple[str, str], ...] = field(default_factory=tuple)

    @property
    def strong_items(self) -> int:
        return len(self.escalated) + len(self.strong_routed)


def simulate_strategy(
    name: str,
    fast: Sequence[Judgment],
    strong: Sequence[Judgment],
    *,
    policy: EscalationPolicy,
    strong_types: Collection[JudgmentType] = (),
) -> StrategyOutcome:
    strong_by = {_key(j): j for j in strong}
    final, escalated, routed, missing = [], [], [], []
    for j in fast:
        request = JudgmentRequest(j.type, j.input)
        if j.type in strong_types:
            routed.append((j.type.value, j.subject))
            replacement = strong_by.get(_key(j))
            if replacement is None:
                missing.append((j.type.value, j.subject))
            final.append(replacement or j)
            continue
        why = policy.reason(request, status=b.OK, structured=_structured(j))
        if why is None:
            final.append(j)
            continue
        escalated.append((j.type.value, j.subject, why[0].value))
        replacement = strong_by.get(_key(j))
        if replacement is None:
            missing.append((j.type.value, j.subject))
        final.append(replacement or j)
    return StrategyOutcome(name, tuple(final), tuple(escalated), tuple(routed), tuple(missing))


class PrecomputedJudgmentProvider:
    """Serves fixed judgment Evidence by input hash (for replaying a simulated strategy)."""

    def __init__(self, evidence: Sequence[Evidence], *, name: str = "anthropic") -> None:
        self.name = name
        self._by_hash = {e.payload["input_hash"]: e for e in evidence}

    def judge(
        self, requests: Sequence[JudgmentRequest], *, marketplace: str, run_id: str | None = None
    ) -> list[Evidence]:
        out: list[Evidence] = []
        for request in requests:
            found = self._by_hash.get(request.input_hash)
            if found is not None and found not in out:
                out.append(found)
        return out


@dataclass(frozen=True, slots=True)
class StrategyCost:
    planned_calls: int  # fast + strong-routed batches, plus the needed escalation calls
    fast_calls: int
    strong_calls: int
    expected_cost_usd: float | None
    worst_case_cost_usd: float | None


def strategy_cost(
    stages: Mapping[str, Sequence[JudgmentRequest]],
    outcome: StrategyOutcome,
    *,
    strong_types: Collection[JudgmentType] = (),
    tiers: ModelTiers | None = None,
    policy: EscalationPolicy | None = None,
    prompt_version: str | None = None,
) -> StrategyCost:
    """Planner prices for one strategy over the given stages' model requests."""
    provider = BatchedJudgmentProvider(
        ScriptedTransport(lambda request: None),
        tiers=tiers,
        escalation=policy or EscalationPolicy(),
        strong_types=strong_types,
        prompt_version=prompt_version,
    )
    escalated = {(t, s) for t, s, _ in outcome.escalated}
    fast_calls = strong_calls = 0
    expected = worst = 0.0
    priced = True
    for requests in stages.values():
        if not requests:
            continue
        plan = provider.plan(requests)
        for call in plan.batches:
            if call.tier == ModelTier.FAST.value:
                fast_calls += 1
            else:
                strong_calls += 1
        flagged = [
            i
            for i in batch_items(requests)
            if (i.request.type.value, i.request.subject) in escalated
        ]
        groups = provider._batches(flagged)  # same batching as a live escalation
        strong_calls += len(groups)
        esc = [provider._planned(ModelTier.STRONG, g, exact=False) for g in groups]
        values = [c.expected_cost_usd for c in plan.batches] + [c.expected_cost_usd for c in esc]
        if any(v is None for v in values) or plan.worst_case_cost_usd is None:
            priced = False
            continue
        expected += sum(values)  # type: ignore[arg-type]
        worst += plan.worst_case_cost_usd
    return StrategyCost(
        fast_calls + strong_calls,
        fast_calls,
        strong_calls,
        expected if priced else None,
        worst if priced else None,
    )
