"""Core domain models.

Everything here is plain, immutable data: no I/O, no network, no LLM calls.
Collections passed in are copied and frozen so a model can't change after
it has been validated.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Any

from atlas_amazon.jsonvalue import freeze

_ASIN = re.compile(r"^[A-Z0-9]{10}$")


def is_valid_asin(value: str) -> bool:
    """ASINs (and ISBN-10s used as book ASINs) are 10 uppercase alphanumerics."""
    return bool(_ASIN.match(value))


class Severity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class SourceStatus(StrEnum):
    """How far a rule's source can be trusted."""

    VERIFIED = "verified"  # checked against the primary source on `as_of`
    UNVERIFIED = "unverified"  # attributed to a primary source, not re-checked
    HEURISTIC = "heuristic"  # a project convention, not an Amazon rule


@dataclass(frozen=True, slots=True)
class SourceRef:
    """Provenance for a rule or limit. Amazon rules change, so every one is dated."""

    id: str
    title: str
    as_of: date
    status: SourceStatus
    url: str | None = None
    marketplace: str | None = None
    scope: str | None = None
    note: str | None = None
    # Non-authoritative references (forums, third-party guides). They never
    # justify a `verified` status and are kept apart from `url` on purpose.
    see_also: tuple[str, ...] = ()


class EvidenceKind(StrEnum):
    """Kinds produced by the provider protocols. `Evidence.kind` is any non-empty str."""

    CATALOG_ITEM = "catalog_item"
    KEYWORD_METRIC = "keyword_metric"
    AUTOCOMPLETE_SUGGESTION = "autocomplete_suggestion"
    REVIEW_SAMPLE = "review_sample"
    REVIEW_THEME = "review_theme"
    JUDGMENT = "judgment"
    SEMANTIC_CALL = "semantic_call"
    CATALOG_SEARCH = "catalog_search"  # one catalog keyword query and its returned ASINs


@dataclass(frozen=True, slots=True)
class Evidence:
    """One observed fact from a provider, kept with where and when it came from.

    `subject` is what the fact is about (an ASIN, a keyword, a suggestion
    seed). `run_id` groups the evidence collected for one product research
    run. The payload is JSON-only and deeply frozen, so a record can be
    written and read back unchanged.
    """

    id: str
    kind: str
    provider: str
    marketplace: str
    retrieved_at: datetime
    payload: Mapping[str, Any] = field(default_factory=dict)
    source_url: str | None = None
    subject: str | None = None
    run_id: str | None = None

    def __post_init__(self) -> None:
        for name in ("id", "kind", "provider", "marketplace"):
            if not getattr(self, name):
                raise ValueError(f"Evidence.{name} must be non-empty")
        for name in ("subject", "run_id", "source_url"):
            if getattr(self, name) == "":
                raise ValueError(f"Evidence.{name} must be None or non-empty")
        if self.retrieved_at.tzinfo is None or self.retrieved_at.utcoffset() is None:
            raise ValueError("Evidence.retrieved_at must be timezone-aware")
        if not isinstance(self.payload, Mapping):
            raise TypeError("Evidence.payload must be a mapping")
        object.__setattr__(self, "payload", freeze(self.payload, "payload"))


@dataclass(frozen=True, slots=True)
class ProductInput:
    """What the user tells us about the product before any research happens."""

    title: str
    recipe_id: str
    marketplace: str = "US"
    asin: str | None = None
    competitor_asins: tuple[str, ...] = ()
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.title.strip():
            raise ValueError("ProductInput.title must be non-empty")
        competitors = tuple(self.competitor_asins)
        for asin in ((self.asin,) if self.asin else ()) + competitors:
            if not is_valid_asin(asin):
                raise ValueError(f"invalid ASIN: {asin!r}")
        if self.asin and self.asin in competitors:
            raise ValueError("a product cannot be its own competitor")
        if len(set(competitors)) != len(competitors):
            raise ValueError("duplicate competitor ASINs")
        object.__setattr__(self, "competitor_asins", competitors)
        object.__setattr__(self, "attributes", MappingProxyType(dict(self.attributes)))


FieldValue = str | tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Listing:
    """Listing content as a recipe-agnostic map of field name to text or list of text.

    Which fields exist and what their limits are is defined by the recipe, not here.
    """

    fields: Mapping[str, FieldValue]

    def __post_init__(self) -> None:
        coerced: dict[str, FieldValue] = {}
        for name, value in dict(self.fields).items():
            if isinstance(value, str):
                coerced[name] = value
            elif isinstance(value, Sequence) and all(isinstance(v, str) for v in value):
                coerced[name] = tuple(value)
            else:
                raise TypeError(f"field {name!r} must be a str or a sequence of str")
        object.__setattr__(self, "fields", MappingProxyType(coerced))

    def segments(self, name: str) -> tuple[str, ...]:
        """Non-empty text pieces of a field: one for text fields, one per item for lists."""
        value = self.fields.get(name)
        if value is None:
            return ()
        if isinstance(value, str):
            return (value,) if value else ()
        return tuple(v for v in value if v)

    def text(self, name: str) -> str:
        return " ".join(self.segments(name))


@dataclass(frozen=True, slots=True)
class Finding:
    """One audit result. `source` says which (dated) rule produced it."""

    rule_id: str
    severity: Severity
    message: str
    field: str | None = None
    observed: Any = None
    limit: Any = None
    source: SourceRef | None = None


@dataclass(frozen=True, slots=True)
class AuditReport:
    recipe_id: str
    findings: tuple[Finding, ...]

    def by_severity(self, severity: Severity) -> tuple[Finding, ...]:
        return tuple(f for f in self.findings if f.severity is severity)

    @property
    def errors(self) -> tuple[Finding, ...]:
        return self.by_severity(Severity.ERROR)

    @property
    def warnings(self) -> tuple[Finding, ...]:
        return self.by_severity(Severity.WARNING)

    @property
    def passed(self) -> bool:
        return not self.errors
