"""Semantic providers: LLM-backed judgments and review themes, with cache, replay,
usage limits, human overrides and evaluation. The core package never imports
the `anthropic` SDK; only `AnthropicTransport` does, lazily."""

from atlas_amazon.semantic.cache import CacheKey, SemanticCache
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
from atlas_amazon.semantic.pricing import ModelPrice, PricingTable
from atlas_amazon.semantic.prompts import PromptTemplate, load_template
from atlas_amazon.semantic.records import SecretLeakError, ensure_no_secrets, find_secrets
from atlas_amazon.semantic.transport import (
    LIVE_ENV_FLAG,
    AnthropicTransport,
    LiveCallsDisabled,
    RecordingTransport,
    ReplayMiss,
    ReplayTransport,
    ScriptedTransport,
    TransportResponse,
)
from atlas_amazon.semantic.usage import (
    BudgetExceeded,
    SemanticBudget,
    SemanticUsageSummary,
    UsageLedger,
)

__all__ = [
    "LIVE_ENV_FLAG",
    "AnthropicTransport",
    "BudgetExceeded",
    "CacheKey",
    "EvaluationReport",
    "HumanJudgmentProvider",
    "JudgmentResolution",
    "LLMJudgmentProvider",
    "LLMReviewThemeProvider",
    "LLMSettings",
    "LiveCallsDisabled",
    "ModelPrice",
    "PricingTable",
    "PromptTemplate",
    "RecordingTransport",
    "ReplayMiss",
    "ReplayTransport",
    "ScriptedTransport",
    "SecretLeakError",
    "SemanticBudget",
    "SemanticCache",
    "SemanticUsageSummary",
    "TransportResponse",
    "UsageLedger",
    "ensure_no_secrets",
    "evaluate_judgments",
    "find_secrets",
    "load_template",
    "render_evaluation_markdown",
    "resolve_judgments",
]
