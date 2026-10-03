from datetime import UTC, datetime

import pytest

from atlas_amazon.models import (
    AuditReport,
    Evidence,
    Finding,
    Listing,
    ProductInput,
    Severity,
    is_valid_asin,
)


def test_evidence_requires_timezone_aware_timestamp():
    with pytest.raises(ValueError, match="timezone-aware"):
        Evidence("e1", "keyword_metric", "test", "US", datetime(2026, 1, 1))


def test_evidence_payload_is_frozen_copy():
    payload = {"volume": 100}
    ev = Evidence("e1", "keyword_metric", "test", "US", datetime(2026, 1, 1, tzinfo=UTC), payload)
    payload["volume"] = 1
    assert ev.payload["volume"] == 100
    with pytest.raises(TypeError):
        ev.payload["volume"] = 2  # type: ignore[index]


def test_evidence_requires_identity_fields():
    with pytest.raises(ValueError, match="provider"):
        Evidence("e1", "kind", "", "US", datetime(2026, 1, 1, tzinfo=UTC))


@pytest.mark.parametrize("asin", ["B0ABCDEF12", "0306406152", "030640615X"])
def test_valid_asins(asin):
    assert is_valid_asin(asin)


@pytest.mark.parametrize("asin", ["b0abcdef12", "B0ABC", "B0ABCDEF123", "B0ABC-EF12"])
def test_invalid_asins(asin):
    assert not is_valid_asin(asin)


def test_product_input_validates_asins():
    with pytest.raises(ValueError, match="invalid ASIN"):
        ProductInput("Widget", "physical-product", competitor_asins=("bad",))
    with pytest.raises(ValueError, match="own competitor"):
        ProductInput(
            "Widget", "physical-product", asin="B0ABCDEF12", competitor_asins=("B0ABCDEF12",)
        )
    with pytest.raises(ValueError, match="duplicate"):
        ProductInput("Widget", "physical-product", competitor_asins=("B0ABCDEF12", "B0ABCDEF12"))


def test_product_input_coerces_competitors_to_tuple():
    p = ProductInput("Widget", "physical-product", competitor_asins=["B0ABCDEF12"])
    assert p.competitor_asins == ("B0ABCDEF12",)


def test_listing_coerces_lists_and_exposes_segments():
    listing = Listing({"title": "Mug", "bullets": ["a", "", "b"], "empty": ""})
    assert listing.fields["bullets"] == ("a", "", "b")
    assert listing.segments("bullets") == ("a", "b")
    assert listing.segments("empty") == ()
    assert listing.segments("missing") == ()
    assert listing.text("bullets") == "a b"


def test_listing_rejects_non_text_values():
    with pytest.raises(TypeError):
        Listing({"title": 5})  # type: ignore[dict-item]
    with pytest.raises(TypeError):
        Listing({"bullets": ["ok", 3]})  # type: ignore[list-item]


def test_audit_report_partitions_by_severity():
    report = AuditReport(
        "r",
        (
            Finding("a", Severity.ERROR, "x"),
            Finding("b", Severity.WARNING, "y"),
            Finding("c", Severity.INFO, "z"),
        ),
    )
    assert [f.rule_id for f in report.errors] == ["a"]
    assert [f.rule_id for f in report.warnings] == ["b"]
    assert not report.passed
    assert AuditReport("r", (Finding("b", Severity.WARNING, "y"),)).passed
