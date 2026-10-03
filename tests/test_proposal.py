from dataclasses import replace
from datetime import datetime, timedelta

import pytest

from atlas_amazon.evidence import InMemoryEvidenceStore
from atlas_amazon.models import Listing, Severity
from atlas_amazon.planner import Proposal, ProposalBasis, validate_proposal
from atlas_amazon.recipes import load_recipe
from conftest import T0, sample_evidence


@pytest.fixture(scope="module")
def product():
    return load_recipe("physical-product")


@pytest.fixture(scope="module")
def book():
    return load_recipe("book")


@pytest.fixture
def store():
    s = InMemoryEvidenceStore()
    s.append_many([sample_evidence(1), sample_evidence(2)])
    return s


BASE = Listing({"title": "Acme Water Bottle", "bullets": ["Leak proof lid"]})


def make(recipe, **overrides):
    fields = {
        "recipe": recipe,
        "target_field": "title",
        "value": "Acme Insulated Water Bottle, 32 oz",
        "rationale": "Adds 'insulated', the top competitor term, to the title.",
        "created_at": T0,
        "evidence_ids": [sample_evidence(1).id, sample_evidence(2).id],
    }
    fields.update(overrides)
    return Proposal.create(**fields)


class TestProposalModel:
    def test_create_records_recipe_and_evidence(self, product):
        p = make(product)
        assert p.recipe_id == "physical-product"
        assert p.recipe_version == product.version
        assert p.basis is ProposalBasis.EVIDENCE
        assert not p.heuristic
        assert p.id.startswith("prop_")
        assert p.created_at == T0

    def test_id_is_deterministic(self, product):
        assert make(product).id == make(product).id
        assert make(product).id != make(product, rationale="Different reason.").id
        assert make(product).id != make(product, created_at=T0 + timedelta(seconds=1)).id

    def test_no_evidence_requires_explicit_heuristic(self, product):
        with pytest.raises(ValueError, match="must be marked heuristic"):
            make(product, evidence_ids=[])
        p = make(product, evidence_ids=[], heuristic=True)
        assert p.heuristic
        assert p.basis is ProposalBasis.HEURISTIC

    def test_heuristic_cannot_cite_evidence(self, product):
        with pytest.raises(ValueError, match="must not cite evidence"):
            make(product, heuristic=True)

    def test_constructor_enforces_the_same_rule(self, product):
        p = make(product)
        with pytest.raises(ValueError):
            replace(p, evidence_ids=())
        with pytest.raises(ValueError):
            replace(p, basis="heuristic")

    @pytest.mark.parametrize(
        ("overrides", "error"),
        [
            ({"rationale": "  "}, ValueError),
            ({"created_at": datetime(2026, 1, 1)}, ValueError),
            ({"target_field": ""}, ValueError),
            ({"evidence_ids": ["ev_a", "ev_a"]}, ValueError),
            ({"value": ["ok", 3]}, TypeError),
        ],
    )
    def test_field_validation(self, product, overrides, error):
        with pytest.raises(error):
            make(product, **overrides)

    def test_list_values_are_frozen(self, product):
        p = make(product, target_field="bullets", value=["One", "Two"])
        assert p.value == ("One", "Two")

    def test_apply_to_does_not_mutate_base(self, product):
        p = make(product)
        candidate = p.apply_to(BASE)
        assert candidate.fields["title"] == p.value
        assert BASE.fields["title"] == "Acme Water Bottle"
        assert candidate.fields["bullets"] == BASE.fields["bullets"]


class TestValidation:
    def test_valid_proposal(self, product, store):
        result = validate_proposal(make(product), recipe=product, base=BASE, evidence=store)
        assert result.valid
        assert result.audit is not None and result.audit.passed
        assert result.candidate.fields["title"] == "Acme Insulated Water Bottle, 32 oz"

    def test_heuristic_proposal_can_be_valid(self, product, store):
        p = make(product, evidence_ids=[], heuristic=True)
        assert validate_proposal(p, recipe=product, base=BASE, evidence=store).valid

    def test_missing_evidence_invalidates(self, product, store):
        p = make(product, evidence_ids=[sample_evidence(1).id, "ev_not_stored"])
        result = validate_proposal(p, recipe=product, base=BASE, evidence=store)
        assert not result.valid
        assert result.missing_evidence == ("ev_not_stored",)

    def test_audit_errors_on_target_field_block(self, product, store):
        p = make(product, value="Acme Bottle! " + "x" * 70)
        result = validate_proposal(p, recipe=product, base=BASE, evidence=store)
        assert not result.valid
        ids = {f.rule_id for f in result.blocking_findings}
        assert {"field_limit.title.max_chars", "title_disallowed_characters"} <= ids
        assert all(f.severity is Severity.ERROR for f in result.blocking_findings)

    def test_warnings_do_not_block(self, product, store):
        p = make(product, value="Acme Water Bottle on sale")
        result = validate_proposal(p, recipe=product, base=BASE, evidence=store)
        assert result.valid
        assert [f.rule_id for f in result.audit.warnings] == ["title_promotional_extended"]

    def test_errors_in_other_fields_do_not_block_but_are_reported(self, product, store):
        broken_base = Listing({"title": "Acme Bottle", "bullets": ["Eco-friendly steel"]})
        result = validate_proposal(make(product), recipe=product, base=broken_base, evidence=store)
        assert result.valid
        assert "bullet_prohibited_claims" in {f.rule_id for f in result.audit.errors}

    def test_blanking_a_required_field_blocks(self, product, store):
        p = make(product, value="   ")
        result = validate_proposal(p, recipe=product, base=BASE, evidence=store)
        assert [f.rule_id for f in result.blocking_findings] == ["required.title"]

    def test_cross_field_rules_are_attributed(self, book, store):
        base = Listing({"title": "T" * 150})
        p = make(book, target_field="subtitle", value="S" * 60)
        result = validate_proposal(p, recipe=book, base=base, evidence=store)
        assert [f.rule_id for f in result.blocking_findings] == ["title_subtitle_length"]
        ok = make(book, target_field="subtitle", value="S" * 49)
        assert validate_proposal(ok, recipe=book, base=base, evidence=store).valid

    @pytest.mark.parametrize(
        ("build", "match"),
        [
            (lambda product, book: make(book), "targets recipe 'book'"),
            (lambda product, book: replace(make(product), recipe_version="0.0.1"), "made against"),
            (lambda product, book: make(product, target_field="colour"), "no field 'colour'"),
            (lambda product, book: make(product, value=["a", "b"]), "expects text"),
            (
                lambda product, book: make(product, target_field="bullets", value="x"),
                "expects list",
            ),
        ],
    )
    def test_structural_problems(self, product, book, store, build, match):
        result = validate_proposal(build(product, book), recipe=product, base=BASE, evidence=store)
        assert not result.valid
        assert result.audit is None
        assert any(match in problem for problem in result.problems)
