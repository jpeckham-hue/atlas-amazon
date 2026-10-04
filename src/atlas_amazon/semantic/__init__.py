"""Semantic providers: LLM-backed judgments and review themes, with cache, replay,
usage limits, human overrides and evaluation. The core package never imports
the `anthropic` SDK; only `AnthropicTransport` does, lazily."""

from atlas_amazon.semantic.batched import BatchedJudgmentProvider, BatchSettings, EscalationEvent
from atlas_amazon.semantic.cache import CacheKey, SemanticCache
from atlas_amazon.semantic.deterministic import RuleJudgmentProvider
from atlas_amazon.semantic.escalation import EscalationPolicy, EscalationReason
from atlas_amazon.semantic.evaluation import (
    EvaluationReport,
    evaluate_judgments,
    render_evaluation_markdown,
)
from atlas_amazon.semantic.human import (
    HumanJudgmentProvider,
    JudgmentResolution,
    resolve_judgments,
)
from atlas_amazon.semantic.llm import LLMJudgmentProvider, LLMReviewThemeProvider, LLMSettings
from atlas_amazon.semantic.plan import (
    PlannedCall,
    RunSemanticPlan,
    SemanticCallPlan,
    render_plan_markdown,
)
from atlas_amazon.semantic.pricing import ModelPrice, PricingTable
from atlas_amazon.semantic.prompts import PromptTemplate, load_template
from atlas_amazon.semantic.records import SecretLeakError, ensure_no_secrets, find_secrets
from atlas_amazon.semantic.tiers import (
    DIRECT_FAST,
    DIRECT_OPUS_STRONG,
    DIRECT_STRONG,
    FAST,
    OPUS_STRONG,
    STRONG,
    ModelTier,
    ModelTiers,
)
from atlas_amazon.semantic.transport import (
    LIVE_ENV_FLAG,
    AnthropicTransport,
    GatewayTransport,
    LiveCallsDisabled,
    RecordingTransport,
    ReplayMiss,
    ReplayTransport,
    ScriptedTransport,
    TransportResponse,
    default_live_transport,
)
from atlas_amazon.semantic.usage import (
    BudgetExceeded,
    SemanticBudget,
    SemanticUsageSummary,
    UsageLedger,
)

__all__ = [
    "DIRECT_FAST",
    "DIRECT_OPUS_STRONG",
    "DIRECT_STRONG",
    "FAST",
    "LIVE_ENV_FLAG",
    "OPUS_STRONG",
    "STRONG",
    "AnthropicTransport",
    "BatchSettings",
    "BatchedJudgmentProvider",
    "BudgetExceeded",
    "CacheKey",
    "EscalationEvent",
    "EscalationPolicy",
    "EscalationReason",
    "EvaluationReport",
    "GatewayTransport",
    "HumanJudgmentProvider",
    "JudgmentResolution",
    "LLMJudgmentProvider",
    "LLMReviewThemeProvider",
    "LLMSettings",
    "LiveCallsDisabled",
    "ModelPrice",
    "ModelTier",
    "ModelTiers",
    "PlannedCall",
    "PricingTable",
    "PromptTemplate",
    "RecordingTransport",
    "ReplayMiss",
    "ReplayTransport",
    "RuleJudgmentProvider",
    "RunSemanticPlan",
    "ScriptedTransport",
    "SecretLeakError",
    "SemanticBudget",
    "SemanticCache",
    "SemanticCallPlan",
    "SemanticUsageSummary",
    "TransportResponse",
    "UsageLedger",
    "default_live_transport",
    "ensure_no_secrets",
    "evaluate_judgments",
    "find_secrets",
    "load_template",
    "render_evaluation_markdown",
    "render_plan_markdown",
    "resolve_judgments",
]
