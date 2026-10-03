"""Typed, validated recipe model. Built only by `loader.load_recipe`."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from atlas_amazon.models import Severity, SourceRef

# The five decomposable signals of the keyword score. Recipes supply one
# weight per signal and the weights must sum to 1.
KEYWORD_SIGNALS = ("relevance", "demand", "competition", "intent", "competitor_coverage")

# Audit checks a recipe rule can use, mapped to the params each one requires.
KNOWN_CHECKS: Mapping[str, tuple[str, ...]] = {
    "word_repetition": ("max_repeats",),
    "prohibited_terms": ("terms",),
    "disallowed_characters": ("characters",),
    "combined_length": ("max_chars",),
    "backend_repetition": (),
    "backend_visible_overlap": ("visible_fields",),
}

# Checks that operate on the recipe's backend field rather than on `fields`.
BACKEND_CHECKS = frozenset({"backend_repetition", "backend_visible_overlap"})

FIELD_LIMITS = (
    "max_chars",
    "max_bytes",
    "min_count",
    "max_count",
    "item_max_chars",
    "item_max_bytes",
)

FIELD_KINDS = frozenset({"text", "list"})
BACKEND_MODES = frozenset({"bytes", "slots"})


@dataclass(frozen=True, slots=True)
class FieldSpec:
    name: str
    kind: str
    required: bool = False
    max_chars: int | None = None
    max_bytes: int | None = None
    min_count: int | None = None
    max_count: int | None = None
    item_max_chars: int | None = None
    item_max_bytes: int | None = None
    source: SourceRef | None = None
    # Per-limit provenance overriding `source`, for fields whose limits are
    # documented in different places or verified to different degrees.
    limit_sources: Mapping[str, SourceRef] = field(default_factory=dict)
    description: str = ""

    def source_for(self, limit: str) -> SourceRef | None:
        return self.limit_sources.get(limit, self.source)


@dataclass(frozen=True, slots=True)
class RuleSpec:
    id: str
    check: str
    severity: Severity
    source: SourceRef
    fields: tuple[str, ...] = ()
    params: Mapping[str, Any] = field(default_factory=dict)
    enabled: bool = True
    description: str = ""


@dataclass(frozen=True, slots=True)
class BackendSpec:
    """Where hidden keywords live and how they're budgeted. Limits come from the field."""

    field_name: str
    mode: str
    source: SourceRef
    count_spaces: bool = True
    stopwords: tuple[str, ...] = ()
    # Shopper-visible fields whose words don't need repeating in the backend
    # (used by backend packing).
    visible_fields: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Recipe:
    id: str
    version: str
    description: str
    lineage: tuple[str, ...]
    fields: Mapping[str, FieldSpec]
    rules: Mapping[str, RuleSpec]
    backend: BackendSpec | None
    keyword_weights: Mapping[str, float]
    coverage_weights: Mapping[str, float]
    research_priorities: tuple[str, ...]
    sources: Mapping[str, SourceRef]

    def enabled_rules(self) -> tuple[RuleSpec, ...]:
        return tuple(r for r in self.rules.values() if r.enabled)
