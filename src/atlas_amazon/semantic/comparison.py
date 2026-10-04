"""Strong-tier comparison: benchmarking only, never the production path.

`run_strong_comparison` asks the strong tier (`BatchedJudgmentProvider` in
`evaluation="strong_only"` mode) the same keyword judgments the production
pipeline answered, and returns both sets side by side:

* production judgments are untouched (fast tier, or strong where the
  escalation policy chose to escalate);
* strong judgments carry a different provider name (`STRONG_EVAL_PROVIDER`)
  and are never fed back into a `ResearchRun` (the provider refuses), so a
  strong answer can never silently overwrite a production one.

`evaluate_tier_comparison` scores each set against the same reference
(fixture or human judgments) separately, plus a head-to-head of strong vs
production.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from atlas_amazon.judgments.contract import Judgment, JudgmentRequest, JudgmentType, parse_judgment
from atlas_amazon.models import Evidence, EvidenceKind
from atlas_amazon.semantic.batched import STRONG_ONLY, BatchedJudgmentProvider, BatchSettings
from atlas_amazon.semantic.cache import SemanticCache
from atlas_amazon.semantic.evaluation import EvaluationReport, evaluate_judgments
from atlas_amazon.semantic.tiers import ModelTiers
from atlas_amazon.semantic.transport import Transport
from atlas_amazon.semantic.usage import UsageLedger

STRONG_EVAL_PROVIDER = "anthropic-strong-eval"
KEYWORD_TYPES = (JudgmentType.RELEVANCE, JudgmentType.INTENT, JudgmentType.ENTITY)


@dataclass(frozen=True, slots=True)
class TierComparison:
    requests: tuple[JudgmentRequest, ...]
    production: tuple[Judgment, ...]
    strong: tuple[Judgment, ...]
    evidence: tuple[Evidence, ...]  # the strong evaluation's own calls and judgments


@dataclass(frozen=True, slots=True)
class TierComparisonReport:
    production: EvaluationReport  # production vs reference
    strong: EvaluationReport  # strong-only vs reference
    head_to_head: EvaluationReport  # strong-only vs production


def comparison_requests(
    judgments: Sequence[Judgment], *, provider: str, types: Sequence[JudgmentType] = KEYWORD_TYPES
) -> list[JudgmentRequest]:
    """The requests a production model provider answered, in order, deduplicated."""
    seen: dict[str, JudgmentRequest] = {}
    for j in judgments:
        if j.provider == provider and j.type in types:
            seen.setdefault(j.input_hash, JudgmentRequest(j.type, j.input))
    return list(seen.values())


def run_strong_comparison(
    transport: Transport,
    production: Sequence[Judgment],
    *,
    marketplace: str,
    run_id: str | None,
    provider: str = "anthropic",
    ledger: UsageLedger | None = None,
    tiers: ModelTiers | None = None,
    batching: BatchSettings | None = None,
    cache: SemanticCache | None = None,
    types: Sequence[JudgmentType] = KEYWORD_TYPES,
    prompt_version: str | None = None,
) -> TierComparison:
    requests = comparison_requests(production, provider=provider, types=types)
    evaluator = BatchedJudgmentProvider(
        transport,
        tiers=tiers,
        batching=batching,
        ledger=ledger,
        cache=cache,
        name=STRONG_EVAL_PROVIDER,
        evaluation=STRONG_ONLY,
        prompt_version=prompt_version,
    )
    evidence = evaluator.judge(requests, marketplace=marketplace, run_id=run_id)
    wanted = {r.input_hash for r in requests}
    strong = tuple(
        j
        for j in (parse_judgment(e) for e in evidence if e.kind == EvidenceKind.JUDGMENT)
        if j.input_hash in wanted
    )
    kept = tuple(j for j in production if j.provider == provider and j.input_hash in wanted)
    return TierComparison(tuple(requests), kept, strong, tuple(evidence))


def evaluate_tier_comparison(
    comparison: TierComparison, reference: Sequence[Judgment], *, reference_label: str = "fixture"
) -> TierComparisonReport:
    return TierComparisonReport(
        production=evaluate_judgments(
            comparison.production,
            reference,
            candidate_label="production",
            reference_label=reference_label,
        ),
        strong=evaluate_judgments(
            comparison.strong,
            reference,
            candidate_label="strong tier",
            reference_label=reference_label,
        ),
        head_to_head=evaluate_judgments(
            comparison.strong,
            comparison.production,
            candidate_label="strong tier",
            reference_label="production",
        ),
    )
