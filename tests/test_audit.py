import pytest

from atlas_amazon.audit import (
    CHECKS,
    audit_listing,
    check_field_limits,
    find_disallowed_characters,
    find_repeated_words,
    find_terms,
)
from atlas_amazon.models import Listing, Severity
from atlas_amazon.recipes import KNOWN_CHECKS, FieldSpec, load_recipe


@pytest.fixture(scope="module")
def product():
    return load_recipe("physical-product")


@pytest.fixture(scope="module")
def book():
    return load_recipe("book")


def rule_ids(report):
    return [f.rule_id for f in report.findings]


def test_check_registry_matches_recipe_schema():
    assert set(CHECKS) == set(KNOWN_CHECKS)


class TestPrimitives:
    def test_find_repeated_words(self):
        text = "Steel Bottle, Steel Lid, Steel Straw for the kids and the adults and the dog"
        assert find_repeated_words(text, 2, exempt=["the", "and"]) == {"steel": 3}
        assert find_repeated_words(text, 3) == {}

    def test_find_terms_matches_plural_folded_phrases(self):
        assert find_terms("Amazon Best Sellers list", ["best seller", "free"]) == ["best seller"]
        assert find_terms("Carefree living", ["free"]) == []  # whole words only

    def test_find_disallowed_characters(self):
        assert find_disallowed_characters("Wow! $5? ok!", "!$?") == ["!", "$", "?"]
        assert find_disallowed_characters("plain", "!$?") == []

    def test_check_field_limits_text_chars_and_bytes(self):
        spec = FieldSpec("st", "text", max_chars=10, max_bytes=8)
        findings = check_field_limits("ééééé", spec)  # 5 chars, 10 bytes
        assert [f.rule_id for f in findings] == ["field_limit.st.max_bytes"]
        assert findings[0].observed == 10

    def test_check_field_limits_list(self):
        spec = FieldSpec("b", "list", min_count=2, max_count=3, item_max_chars=5)
        assert [f.rule_id for f in check_field_limits(("ok",), spec)] == ["field_limit.b.min_count"]
        findings = check_field_limits(("a", "b", "c", "toolong"), spec)
        assert [f.rule_id for f in findings] == [
            "field_limit.b.max_count",
            "field_limit.b.item.max_chars",
        ]
        assert "b[3]" in findings[1].message

    def test_check_field_limits_kind_mismatch(self):
        assert check_field_limits(("x",), FieldSpec("t", "text"))[0].rule_id == "field_limit.t.kind"
        assert check_field_limits("x", FieldSpec("l", "list"))[0].rule_id == "field_limit.l.kind"


class TestAuditPhysicalProduct:
    def test_clean_listing_passes(self, product):
        listing = Listing(
            {
                "title": "Acme Insulated Water Bottle, 32 oz Stainless Steel",
                "brand": "Acme",
                "bullets": ["Keeps drinks cold for 24 hours", "Leak-proof lid"],
                "description": "A sturdy bottle.",
                "search_terms": "hydro flask gym hiking camping",
            }
        )
        report = audit_listing(listing, product)
        assert report.findings == ()
        assert report.passed

    def test_missing_required_title(self, product):
        report = audit_listing(Listing({"title": "  "}), product)
        assert rule_ids(report) == ["required.title"]
        assert not report.passed

    def test_title_rules_and_provenance(self, product):
        listing = Listing({"title": "Best Seller! Bottle Bottle Bottle - Free Shipping"})
        report = audit_listing(listing, product)
        ids = rule_ids(report)
        assert "title_word_repetition" in ids
        assert "title_disallowed_characters" in ids
        promo = next(f for f in report.findings if f.rule_id == "promotional_terms")
        assert promo.observed == ["best seller", "free shipping"]
        assert promo.source.id == "amazon-title-policy-2025"
        assert promo.source.as_of.year == 2025

    def test_promotional_terms_checked_per_bullet(self, product):
        listing = Listing({"title": "Bottle", "bullets": ["Great value", "Top rated by users"]})
        report = audit_listing(listing, product)
        assert [f.field for f in report.findings if f.rule_id == "promotional_terms"] == ["bullets"]

    def test_backend_byte_limit(self, product):
        listing = Listing({"title": "Bottle", "search_terms": "é" * 126})  # 252 bytes
        report = audit_listing(listing, product)
        assert "field_limit.search_terms.max_bytes" in rule_ids(report)

    def test_too_many_bullets(self, product):
        listing = Listing({"title": "Bottle", "bullets": ["a"] * 6})
        assert "field_limit.bullets.max_count" in rule_ids(audit_listing(listing, product))

    def test_backend_redundancy(self, product):
        listing = Listing(
            {
                "title": "Water Bottle",
                "bullets": ["Leak proof"],
                "search_terms": "bottles gym for for gym hiking",
            }
        )
        report = audit_listing(listing, product)
        redundancy = [f for f in report.findings if f.rule_id == "backend_redundancy"]
        assert all(f.severity is Severity.WARNING for f in redundancy)
        assert redundancy[0].observed == ["bottles"]
        assert redundancy[1].observed == ["gym"]  # "for" is a stopword
        assert report.passed  # warnings don't fail an audit

    def test_unknown_fields_reported_as_info(self, product):
        report = audit_listing(Listing({"title": "Bottle", "colour": "red"}), product)
        assert rule_ids(report) == ["unknown_field.colour"]
        assert report.findings[0].severity is Severity.INFO
        assert report.passed


class TestAuditBook:
    def test_book_title_rules_relaxed(self, book):
        listing = Listing({"title": "Run, Run, Run! What Happens Next?"})
        report = audit_listing(listing, book)
        assert report.findings == ()

    def test_title_subtitle_combined_length(self, book):
        listing = Listing({"title": "T" * 120, "subtitle": "S" * 90})
        report = audit_listing(listing, book)
        assert rule_ids(report) == ["title_subtitle_length"]
        assert report.findings[0].observed == 210

    def test_kdp_keyword_rules(self, book):
        listing = Listing(
            {
                "title": "The Quiet Harbor",
                "keywords": ["cozy mystery", "free kindle unlimited books", "k" * 51] + ["x"] * 5,
            }
        )
        ids = rule_ids(audit_listing(listing, book))
        assert "field_limit.keywords.max_count" in ids
        assert "field_limit.keywords.item.max_chars" in ids
        assert "kdp_keyword_terms" in ids

    def test_book_has_no_bullets_field(self, book):
        report = audit_listing(Listing({"title": "X", "bullets": ["a"]}), book)
        assert rule_ids(report) == ["unknown_field.bullets"]
