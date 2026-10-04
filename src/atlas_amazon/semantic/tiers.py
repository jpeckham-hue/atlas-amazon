"""Model tiers for semantic calls.

Live calls go through Vercel AI Gateway by default (see `transport`), so the
default tiers use **gateway model IDs** (`anthropic/claude-haiku-4.5`,
`anthropic/claude-sonnet-5.5`) and pin the routed provider to Anthropic with
`providerOptions.gateway.only = ["anthropic"]`. The pin is part of the
request body, so it is recorded and hashed: pricing and feature support
(structured outputs, `between_tools`) are those of Anthropic's own API,
never a silently substituted provider. `DIRECT_FAST` / `DIRECT_STRONG` /
`DIRECT_OPUS_STRONG` are the same settings with Anthropic API model IDs for
the optional direct transport.

Two tiers, each an `LLMSettings`:

* `fast` (default **Claude Haiku 4.5**, $1 / $5 per MTok): routine relevance,
  intent and entity classification, and equivalence pairs. Haiku 4.5
  supports structured outputs. It rejects the `effort` parameter and does not
  think unless asked, so its output is bounded by the structured answer
  alone.
* `strong` (default **Claude Sonnet 5.5**, $2 / $10 per MTok): escalated
  items only (see `escalation.EscalationPolicy`). It runs at `effort: low`
  with `thinking: {"type": "between_tools"}`, Sonnet 5.5's lowest thinking
  setting (no extended thinking), so output stays bounded by the answer.
  `between_tools` is Sonnet-5.5-only, and a server-side refusal fallback may
  re-run the request on another model, so this tier does not request
  fallbacks. A refused item simply keeps its fast-tier answer (or falls back
  to the explicit heuristics).

Claude Opus 5.5 is no longer the default: it always thinks, which makes
output (and so cost) hard to bound for one-line classifications. It remains
available as `OPUS_STRONG`, with a `thinking_allowance` reserved in every
output budget.

Every judgment records the model that actually served it (`model`) and the
model and tier that were requested (`call.requested_model`, `call.tier`).
Which tier is good enough is an empirical question: compare tiers against
the fixture judgments with `evaluate_judgments` once live recordings exist.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from atlas_amazon.jsonvalue import freeze

EFFORT_LEVELS = ("low", "medium", "high", "xhigh", "max")
# Vercel AI Gateway model IDs (the default live route).
FAST_MODEL = "anthropic/claude-haiku-4.5"
STRONG_MODEL = "anthropic/claude-sonnet-5.5"
OPUS_MODEL = "anthropic/claude-opus-5.5"
# The same models on the direct Anthropic API.
DIRECT_FAST_MODEL = "claude-haiku-4-5"
DIRECT_STRONG_MODEL = "claude-sonnet-5-5"
DIRECT_OPUS_MODEL = "claude-opus-5-5"
# Gateway routing: only Anthropic may serve these requests.
ANTHROPIC_ONLY = {"gateway": {"only": ["anthropic"]}}


class ModelTier(StrEnum):
    FAST = "fast"
    STRONG = "strong"


@dataclass(frozen=True, slots=True)
class LLMSettings:
    """How one model is called. See the FAST / STRONG presets for the configured tiers."""

    model: str = FAST_MODEL
    effort: str | None = None  # None: omit `output_config.effort` (Haiku 4.5 rejects it)
    refusal_fallbacks: bool = False  # server-side fallback on safety declines
    thinking: Mapping[str, Any] | None = None  # sent as-is, e.g. {"type": "between_tools"}
    # Output tokens reserved on top of the structured answer, for models that
    # always think (Opus 5.5). Counted by max_tokens and so by cost guards.
    thinking_allowance: int = 0
    # Vercel AI Gateway routing, sent as the request's `providerOptions`.
    provider_options: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.model, str) or not self.model:
            raise ValueError("model must be a non-empty string")
        if self.effort is not None and self.effort not in EFFORT_LEVELS:
            raise ValueError(f"unknown effort {self.effort!r}")
        if self.thinking_allowance < 0:
            raise ValueError("thinking_allowance must be >= 0")
        if self.provider_options is not None:
            object.__setattr__(
                self, "provider_options", freeze(self.provider_options, "provider_options")
            )
        if self.thinking is not None:
            object.__setattr__(self, "thinking", freeze(self.thinking, "thinking"))
            if self.thinking.get("type") == "between_tools" and self.refusal_fallbacks:
                raise ValueError(
                    "thinking 'between_tools' is accepted only by Claude Sonnet 5.5; "
                    "a refusal fallback could re-run the request on another model"
                )


FAST = LLMSettings(FAST_MODEL, provider_options=ANTHROPIC_ONLY)
STRONG = LLMSettings(
    STRONG_MODEL,
    effort="low",
    thinking={"type": "between_tools"},
    provider_options=ANTHROPIC_ONLY,
)
OPUS_STRONG = LLMSettings(
    OPUS_MODEL, effort="low", thinking_allowance=2048, provider_options=ANTHROPIC_ONLY
)
DIRECT_FAST = LLMSettings(DIRECT_FAST_MODEL)
DIRECT_STRONG = LLMSettings(DIRECT_STRONG_MODEL, effort="low", thinking={"type": "between_tools"})
# Server-side refusal fallbacks are an Anthropic API beta, so only the direct
# Opus preset requests them.
DIRECT_OPUS_STRONG = LLMSettings(
    DIRECT_OPUS_MODEL, effort="low", refusal_fallbacks=True, thinking_allowance=2048
)


@dataclass(frozen=True, slots=True)
class ModelTiers:
    fast: LLMSettings = field(default_factory=lambda: FAST)
    strong: LLMSettings = field(default_factory=lambda: STRONG)

    def __getitem__(self, tier: ModelTier | str) -> LLMSettings:
        return self.fast if ModelTier(tier) is ModelTier.FAST else self.strong
