"""Semantic usage accounting and hard limits.

A `UsageLedger` records one `UsageRecord` per API call (live or replayed),
per cache hit and per skipped call: tokens, estimated cost and outcome. A
batched call covers several judgments (`items`), produces some valid ones
(`judgments`) and may be an escalation to the strong tier (`escalated`).
Item-level failures inside a call (missing, duplicate, malformed results)
are counted in `item_failures`, so one bad item never hides the rest. A
ledger may be shared by the judgment and review-theme providers, so the
limits cover both.

**Limits** (`SemanticBudget`, per run_id) are enforced *before* each live
call:

* `max_live_calls`: the next call is refused once this many live calls
  have been made in the run;
* `max_cost_usd`: the next call is refused unless the spend so far plus a
  **worst-case** estimate of the next call (estimated input tokens plus the
  full `max_tokens` of output) fits. If the model has no configured price,
  the cost can't be bounded, so the call is refused.

A refusal raises `BudgetExceeded`. Providers catch it, stop making calls
for the rest of the batch, and record the halt. Unanswered requests fall
back to the explicit heuristics, so a run degrades instead of overspending.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from atlas_amazon.jsonvalue import canonical_json
from atlas_amazon.semantic.pricing import PricingTable

CHARS_PER_TOKEN = 4  # rough estimate, used only for pre-call budget checks


def estimate_tokens(data: Any) -> int:
    """Rough token estimate from serialized size. Used for limits, never for billing."""
    return max(1, len(canonical_json(data)) // CHARS_PER_TOKEN)


class BudgetExceeded(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True, slots=True)
class SemanticBudget:
    max_live_calls: int | None = None
    max_cost_usd: float | None = None

    def __post_init__(self) -> None:
        if self.max_live_calls is not None and self.max_live_calls < 0:
            raise ValueError("max_live_calls must be >= 0")
        if self.max_cost_usd is not None and self.max_cost_usd < 0:
            raise ValueError("max_cost_usd must be >= 0")


@dataclass(frozen=True, slots=True)
class UsageRecord:
    run_id: str | None
    provider: str
    model: str  # model that served the request (or was requested, for cache/replay misses)
    purpose: str  # "judgment:relevance", "review_themes", ...
    prompt_version: str
    source: str  # "live" | "cache" | "replay" | "skipped"
    outcome: str  # "ok" | "malformed" | "refusal" | "replay_miss" | "error" | "budget"
    input_tokens: int | None = None
    output_tokens: int | None = None
    cache_read_tokens: int | None = None
    cache_write_tokens: int | None = None
    estimated_cost_usd: float | None = None
    detail: str = ""
    tier: str | None = None  # "fast" | "strong" (None: single-model provider)
    items: int = 1  # judgments covered by this call (batch size)
    judgments: int = 0  # valid item answers it produced (an escalated item counts per call)
    escalated: int = 0  # items in this call that were escalated from the fast tier
    item_failures: tuple[tuple[str, int], ...] = ()  # (item outcome, count)

    @property
    def is_call(self) -> bool:
        return self.source in ("live", "replay")


@dataclass(frozen=True, slots=True)
class UsageGroup:
    provider: str
    model: str
    requests: int
    live_calls: int
    replayed: int
    cache_hits: int
    cache_misses: int  # live or replayed requests that were not served from cache
    failures: Mapping[str, int]  # outcome -> count, excluding "ok"
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float | None  # None when any priced call had unknown pricing
    fast_calls: int = 0
    strong_calls: int = 0
    escalations: int = 0
    judgments: int = 0  # valid judgments from live or replayed calls


@dataclass(frozen=True, slots=True)
class SemanticUsageSummary:
    """Usage for one run. The run fills in the fields after `pricing_as_of`.

    `estimated_cost_usd` is *measured*: API-reported tokens of live calls times
    list prices (0 without live calls). `expected_cost_usd`
    and `worst_case_cost_usd` come from the call plans.
    """

    groups: tuple[UsageGroup, ...]
    halts: tuple[str, ...]  # budget refusals, in order
    budget: SemanticBudget
    pricing_as_of: str
    model_judgments: int = 0  # final judgments supplied by the model provider (cache included)
    human_overrides: int = 0  # requests answered by a human, never sent to a model
    deterministic_judgments: int = 0  # requests answered by recipe/keyword rules
    skipped_judgments: int = 0  # requests not needed (e.g. families that cannot be ranked)
    planned_calls: int | None = None
    expected_cost_usd: float | None = None
    worst_case_cost_usd: float | None = None

    @property
    def live_calls(self) -> int:
        return sum(g.live_calls for g in self.groups)

    @property
    def replayed_calls(self) -> int:
        return sum(g.replayed for g in self.groups)

    @property
    def api_calls(self) -> int:
        """Live calls plus replayed ones (each replay stands for one recorded API call)."""
        return self.live_calls + self.replayed_calls

    @property
    def cache_hits(self) -> int:
        return sum(g.cache_hits for g in self.groups)

    @property
    def fast_calls(self) -> int:
        return sum(g.fast_calls for g in self.groups)

    @property
    def strong_calls(self) -> int:
        return sum(g.strong_calls for g in self.groups)

    @property
    def escalations(self) -> int:
        return sum(g.escalations for g in self.groups)

    @property
    def judgments_produced(self) -> int:
        return sum(g.judgments for g in self.groups)

    @property
    def input_tokens(self) -> int:
        return sum(g.input_tokens for g in self.groups)

    @property
    def output_tokens(self) -> int:
        return sum(g.output_tokens for g in self.groups)

    @property
    def estimated_cost_usd(self) -> float | None:
        costs = [g.estimated_cost_usd for g in self.groups if g.live_calls]
        return None if any(c is None for c in costs) else sum(costs)  # type: ignore[arg-type]

    @property
    def measured_cost_per_judgment(self) -> float | None:
        """Live cost per final model judgment; None without live calls (nothing measured)."""
        cost = self.estimated_cost_usd
        if not self.live_calls or cost is None or not self.model_judgments:
            return None
        return cost / self.model_judgments

    @property
    def expected_cost_per_judgment(self) -> float | None:
        """Planned expected cost per final model judgment."""
        cost = self.expected_cost_usd
        return None if cost is None or not self.model_judgments else cost / self.model_judgments


@dataclass
class UsageLedger:
    budget: SemanticBudget = field(default_factory=SemanticBudget)
    pricing: PricingTable = field(default_factory=PricingTable)
    records: list[UsageRecord] = field(default_factory=list)
    halts: list[tuple[str | None, str]] = field(default_factory=list)

    # -- limits -----------------------------------------------------------------

    def _spent(self, run_id: str | None) -> tuple[int, float, bool]:
        calls, cost, unknown = 0, 0.0, False
        for r in self.records:
            if r.run_id == run_id and r.source == "live":
                calls += 1
                if r.estimated_cost_usd is None:
                    unknown = True
                else:
                    cost += r.estimated_cost_usd
        return calls, cost, unknown

    def authorize(self, *, run_id: str | None, model: str, request: Mapping[str, Any]) -> None:
        """Raise BudgetExceeded if the next live call could break a configured limit."""
        calls, spent, unknown = self._spent(run_id)
        limit_calls, limit_cost = self.budget.max_live_calls, self.budget.max_cost_usd
        if limit_calls is not None and calls >= limit_calls:
            self._halt(run_id, f"max_live_calls={limit_calls} reached")
        if limit_cost is not None:
            price = self.pricing.get(model)
            if price is None or unknown:
                self._halt(
                    run_id, f"cannot bound cost for model {model!r} under max_cost_usd={limit_cost}"
                )
            worst = price.cost(estimate_tokens(request), int(request.get("max_tokens", 0)))
            if spent + worst > limit_cost:
                self._halt(
                    run_id,
                    f"max_cost_usd={limit_cost} would be exceeded "
                    f"(spent ${spent:.4f}, next call up to ${worst:.4f})",
                )

    def _halt(self, run_id: str | None, reason: str) -> None:
        self.halts.append((run_id, reason))
        raise BudgetExceeded(reason)

    # -- recording --------------------------------------------------------------

    def cost_of(self, model: str, usage: Mapping[str, Any]) -> float | None:
        price = self.pricing.get(model)
        if price is None:
            return None
        return price.cost(
            int(usage.get("input_tokens") or 0),
            int(usage.get("output_tokens") or 0),
            int(usage.get("cache_read_input_tokens") or 0),
            int(usage.get("cache_creation_input_tokens") or 0),
        )

    def record(self, record: UsageRecord) -> None:
        self.records.append(record)

    def summary(self, run_id: str | None) -> SemanticUsageSummary:
        grouped: dict[tuple[str, str], list[UsageRecord]] = defaultdict(list)
        for r in self.records:
            if r.run_id == run_id:
                grouped[(r.provider, r.model)].append(r)
        groups = []
        for (provider, model), items in sorted(grouped.items()):
            live = [r for r in items if r.source == "live"]
            costs = [r.estimated_cost_usd for r in live]
            failures: dict[str, int] = {}
            for r in items:
                if r.outcome not in ("ok", "partial"):
                    failures[r.outcome] = failures.get(r.outcome, 0) + 1
                for status, n in r.item_failures:
                    failures[f"item_{status}"] = failures.get(f"item_{status}", 0) + n
            groups.append(
                UsageGroup(
                    provider=provider,
                    model=model,
                    requests=len(items),
                    live_calls=len(live),
                    replayed=sum(1 for r in items if r.source == "replay"),
                    cache_hits=sum(1 for r in items if r.source == "cache"),
                    cache_misses=sum(1 for r in items if r.source in ("live", "replay")),
                    failures=dict(sorted(failures.items())),
                    input_tokens=sum(r.input_tokens or 0 for r in items if r.source != "cache"),
                    output_tokens=sum(r.output_tokens or 0 for r in items if r.source != "cache"),
                    estimated_cost_usd=None if any(c is None for c in costs) else sum(costs),
                    fast_calls=sum(1 for r in items if r.is_call and r.tier == "fast"),
                    strong_calls=sum(1 for r in items if r.is_call and r.tier == "strong"),
                    escalations=sum(r.escalated for r in items if r.is_call),
                    judgments=sum(r.judgments for r in items if r.is_call),
                )
            )
        return SemanticUsageSummary(
            groups=tuple(groups),
            halts=tuple(reason for rid, reason in self.halts if rid == run_id),
            budget=self.budget,
            pricing_as_of=self.pricing.as_of,
        )


@dataclass(frozen=True, slots=True)
class CostEstimate:
    """Offline cost estimate for replaying a recording's requests on a priced model."""

    model: str
    calls: int
    input_tokens: int  # estimated from request size (chars / 4)
    output_tokens: int  # estimated from recorded response text (chars / 4)
    estimated_cost_usd: float
    worst_case_cost_usd: float  # every call uses its full max_tokens of output
    note: str = (
        "Estimate only: token counts are approximated from text size, and adaptive "
        "thinking tokens (always on for Claude Opus 5.5) are not included in the "
        "expected figure; they are covered by the worst case."
    )


def estimate_recording_cost(
    path, model: str | None = None, pricing: PricingTable | None = None
) -> CostEstimate:
    """Price a recording's requests offline.

    With `model`, every request is priced as if sent to that model. With
    None, each request is priced at the model it actually requested (a
    tiered recording mixes fast and strong models).
    """
    from atlas_amazon.semantic.records import ChecksummedJsonl

    table = pricing or PricingTable()
    records = ChecksummedJsonl(path).read()
    inp = out = 0
    expected = worst = 0.0
    for record in records:
        request = record["request"]
        name = model or request["model"]
        price = table.get(name)
        if price is None:
            raise ValueError(f"no price configured for {name!r}")
        i = estimate_tokens(request)
        o = estimate_tokens(record["response"].get("text") or "")
        inp, out = inp + i, out + o
        expected += price.cost(i, o)
        worst += price.cost(i, int(request.get("max_tokens", 0)))
    return CostEstimate(model or "as requested", len(records), inp, out, expected, worst)
