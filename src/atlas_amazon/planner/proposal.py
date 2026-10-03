"""Proposals: one suggested change to one listing field, with its justification.

A Proposal is immutable and carries no validity flag of its own. The only
way to establish validity is `validate_proposal`, which:

1. checks the proposal targets the given recipe (ID and version) and a
   field the recipe defines, with the right shape (text vs list);
2. checks every cited evidence ID exists in the evidence store;
3. applies the value to the base listing and runs the existing
   deterministic audit (`audit_listing`) on the result.

The proposal is valid only if all three pass, with no error-severity audit
finding attributable to the target field. Errors in other fields belong to
the base listing, not to the proposal. They are reported in the full audit
but don't block it.

Evidence-free proposals are allowed only when explicitly marked
`ProposalBasis.HEURISTIC`. The constructor refuses an evidence-free
proposal claiming any other basis, and an evidence-backed proposal
claiming to be heuristic.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas_amazon.audit.listing import audit_listing
from atlas_amazon.evidence.store import EvidenceStore
from atlas_amazon.jsonvalue import canonical_json
from atlas_amazon.models import AuditReport, FieldValue, Finding, Listing, Severity
from atlas_amazon.recipes.schema import Recipe

ID_PREFIX = "prop_"


class ProposalBasis(StrEnum):
    EVIDENCE = "evidence"
    HEURISTIC = "heuristic"


@dataclass(frozen=True, slots=True)
class Proposal:
    id: str
    recipe_id: str
    recipe_version: str
    target_field: str
    value: FieldValue
    rationale: str
    evidence_ids: tuple[str, ...]
    basis: ProposalBasis
    created_at: datetime

    def __post_init__(self) -> None:
        for name in ("id", "recipe_id", "recipe_version", "target_field"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name):
                raise ValueError(f"Proposal.{name} must be a non-empty string")
        if not isinstance(self.rationale, str) or not self.rationale.strip():
            raise ValueError("Proposal.rationale must explain why the change is proposed")
        if isinstance(self.value, str):
            value: FieldValue = self.value
        elif isinstance(self.value, Sequence) and all(isinstance(v, str) for v in self.value):
            value = tuple(self.value)
        else:
            raise TypeError("Proposal.value must be a str or a sequence of str")
        ids = tuple(self.evidence_ids)
        if any(not isinstance(i, str) or not i for i in ids) or len(set(ids)) != len(ids):
            raise ValueError("Proposal.evidence_ids must be unique non-empty strings")
        basis = ProposalBasis(self.basis)
        if not ids and basis is not ProposalBasis.HEURISTIC:
            raise ValueError("a proposal without evidence must be marked heuristic")
        if ids and basis is ProposalBasis.HEURISTIC:
            raise ValueError("a heuristic proposal must not cite evidence")
        if self.created_at.utcoffset() is None:
            raise ValueError("Proposal.created_at must be timezone-aware")
        object.__setattr__(self, "value", value)
        object.__setattr__(self, "evidence_ids", ids)
        object.__setattr__(self, "basis", basis)

    @classmethod
    def create(
        cls,
        *,
        recipe: Recipe,
        target_field: str,
        value: FieldValue | Sequence[str],
        rationale: str,
        created_at: datetime,
        evidence_ids: Sequence[str] = (),
        heuristic: bool = False,
    ) -> Proposal:
        """Build a proposal against `recipe` with a deterministic, content-derived ID.

        Pass `heuristic=True` to propose without evidence. It has to be said
        explicitly.
        """
        basis = ProposalBasis.HEURISTIC if heuristic else ProposalBasis.EVIDENCE
        frozen_value = value if isinstance(value, str) else tuple(value)
        identity = {
            "recipe_id": recipe.id,
            "recipe_version": recipe.version,
            "target_field": target_field,
            "value": frozen_value,
            "rationale": rationale,
            "evidence_ids": list(evidence_ids),
            "basis": basis.value,
            "created_at": created_at.isoformat(),
        }
        digest = hashlib.sha256(canonical_json(identity).encode("utf-8")).hexdigest()
        return cls(
            id=ID_PREFIX + digest[:24],
            recipe_id=recipe.id,
            recipe_version=recipe.version,
            target_field=target_field,
            value=frozen_value,
            rationale=rationale,
            evidence_ids=tuple(evidence_ids),
            basis=basis,
            created_at=created_at,
        )

    @property
    def heuristic(self) -> bool:
        return self.basis is ProposalBasis.HEURISTIC

    def apply_to(self, listing: Listing) -> Listing:
        """A new Listing with the target field replaced. The original is untouched."""
        return Listing({**listing.fields, self.target_field: self.value})


@dataclass(frozen=True, slots=True)
class ProposalValidation:
    proposal: Proposal
    candidate: Listing | None  # the base listing with the proposal applied
    audit: AuditReport | None  # full audit of `candidate`
    problems: tuple[str, ...]  # recipe/shape/evidence problems found before the audit
    missing_evidence: tuple[str, ...]
    blocking_findings: tuple[Finding, ...]  # audit errors attributable to the target field

    @property
    def valid(self) -> bool:
        return (
            self.audit is not None
            and not self.problems
            and not self.missing_evidence
            and not self.blocking_findings
        )


def _attributable(finding: Finding, target: str, recipe: Recipe) -> bool:
    if finding.field == target:
        return True
    if finding.field is None:
        # Cross-field rules (e.g. combined_length) report no single field.
        rule = recipe.rules.get(finding.rule_id)
        return rule is not None and target in rule.fields
    return False


def validate_proposal(
    proposal: Proposal,
    *,
    recipe: Recipe,
    base: Listing,
    evidence: EvidenceStore,
) -> ProposalValidation:
    problems: list[str] = []
    if proposal.recipe_id != recipe.id:
        problems.append(f"proposal targets recipe {proposal.recipe_id!r}, not {recipe.id!r}")
    elif proposal.recipe_version != recipe.version:
        problems.append(
            f"proposal was made against {recipe.id} {proposal.recipe_version}, "
            f"recipe is now {recipe.version}"
        )
    spec = recipe.fields.get(proposal.target_field)
    if spec is None:
        problems.append(f"recipe {recipe.id!r} has no field {proposal.target_field!r}")
    elif (spec.kind == "text") != isinstance(proposal.value, str):
        problems.append(f"field {spec.name!r} expects {spec.kind} but the value is not")
    missing = tuple(i for i in proposal.evidence_ids if i not in evidence)

    if problems:
        return ProposalValidation(proposal, None, None, tuple(problems), missing, ())
    candidate = proposal.apply_to(base)
    report = audit_listing(candidate, recipe)
    blocking = tuple(
        f
        for f in report.findings
        if f.severity is Severity.ERROR and _attributable(f, proposal.target_field, recipe)
    )
    return ProposalValidation(proposal, candidate, report, (), missing, blocking)
