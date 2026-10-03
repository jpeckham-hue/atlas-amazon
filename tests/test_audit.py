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
        listing = Listing({"title": "Bottle! Bottle Bottle - Free Shipping, Best Seller"})
        report = audit_listing(listing, product)
        ids = rule_ids(report)
        assert "title_word_repetition" in ids
        assert "title_disallowed_characters" in ids
        promo = next(f for f in report.findings if f.rule_id == "title_promotional_phrases")
        assert promo.observed == ["free shipping"]
        assert promo.severity is Severity.ERROR
        assert promo.source.url.endswith("GYTR6SYGFA5E3EQC")
        subjective = next(f for f in report.findings if f.rule_id == "title_subjective_commentary")
        assert subjective.severity is Severity.WARNING

    def test_title_75_character_limit(self, product):
        ok = audit_listing(Listing({"title": "x" * 75}), product)
        assert ok.findings == ()
        report = audit_listing(Listing({"title": "x" * 76}), product)
        assert rule_ids(report) == ["field_limit.title.max_chars"]
        assert report.findings[0].limit == 75
        assert report.findings[0].source.id == "sc-title-requirements"

    def test_item_highlights_limit(self, product):
        listing = Listing({"title": "Bottle", "item_highlights": "y" * 126})
        assert rule_ids(audit_listing(listing, product)) == [
            "field_limit.item_highlights.max_chars"
        ]

    def test_verbatim_examples_are_detected(self, product):
        listing = Listing(
            {
                "title": "Bottle 100% Quality Guaranteed, FSA/HSA Eligible",
                "bullets": ["Eco-friendly steel", "Full refund if broken", "TBD", "Acme™ lid"],
            }
        )
        ids = rule_ids(audit_listing(listing, product))
        for rule_id in (
            "title_promotional_phrases",
            "title_restricted_phrases",
            "bullet_prohibited_claims",
            "bullet_guarantee_information",
            "bullet_placeholder_text",
            "bullet_special_characters",
        ):
            assert rule_id in ids

    def test_atlas_extended_terms_are_warnings_from_heuristic_source(self, product):
        report = audit_listing(Listing({"title": "Bottle on sale"}), product)
        [finding] = report.findings
        assert finding.rule_id == "title_promotional_extended"
        assert finding.severity is Severity.WARNING
        assert finding.source.status.value == "heuristic"
        assert report.passed

    def test_backend_byte_limit_is_less_than_250(self, product):
        ok = audit_listing(Listing({"title": "Bottle", "search_terms": "a" * 249}), product)
        assert ok.findings == ()
        report = audit_listing(Listing({"title": "Bottle", "search_terms": "a" * 250}), product)
        assert rule_ids(report) == ["field_limit.search_terms.max_bytes"]
        multibyte = Listing({"title": "Bottle", "search_terms": "é" * 125})  # 250 bytes
        assert "field_limit.search_terms.max_bytes" in rule_ids(audit_listing(multibyte, product))

    def test_too_many_bullets_cites_unverified_source(self, product):
        listing = Listing({"title": "Bottle", "bullets": ["a"] * 6})
        report = audit_listing(listing, product)
        finding = next(f for f in report.findings if f.rule_id == "field_limit.bullets.max_count")
        assert finding.source.status.value == "unverified"

    def test_backend_rules(self, product):
        listing = Listing(
            {
                "title": "Water Bottle",
                "bullets": ["Leak proof"],
                "search_terms": "bottles gym for for gym hiking cheapest",
            }
        )
        report = audit_listing(listing, product)
        by_rule = {f.rule_id: f for f in report.findings}
        assert by_rule["backend_repetition"].observed == ["gym"]  # "for" is a stopword
        assert by_rule["backend_repetition"].severity is Severity.WARNING
        assert by_rule["backend_visible_overlap"].observed == ["bottles"]
        assert by_rule["backend_visible_overlap"].source.status.value == "heuristic"
        assert by_rule["backend_prohibited_terms"].observed == ["cheapest"]
        assert not report.passed

    def test_backend_singular_and_plural_count_as_repetition(self, product):
        listing = Listing({"title": "Mug", "search_terms": "cup cups"})
        report = audit_listing(listing, product)
        assert rule_ids(report) == ["backend_repetition"]

    def test_unknown_fields_reported_as_info(self, product):
        report = audit_listing(Listing({"title": "Bottle", "colour": "red"}), product)
        assert rule_ids(report) == ["unknown_field.colour"]
        assert report.findings[0].severity is Severity.INFO
        assert report.passed


class TestAuditBook:
    def test_seller_central_title_rules_do_not_apply(self, book):
        # Long, repetitive, "?!" titles are fine for KDP if they match the cover.
        title = "Run, Run, Run! What Happens Next? A Novel of Long Titles and Longer Nights at Sea"
        report = audit_listing(Listing({"title": title}), book)
        assert len(title) > 75
        assert report.findings == ()

    def test_title_subtitle_fewer_than_200(self, book):
        ok = audit_listing(Listing({"title": "T" * 120, "subtitle": "S" * 79}), book)
        assert ok.findings == ()
        report = audit_listing(Listing({"title": "T" * 120, "subtitle": "S" * 80}), book)
        assert rule_ids(report) == ["title_subtitle_length"]
        assert report.findings[0].observed == 200

    def test_title_promotional_reference_is_a_warning(self, book):
        report = audit_listing(Listing({"title": "Born Free"}), book)
        [finding] = report.findings
        assert finding.rule_id == "title_promotional_references"
        assert finding.severity is Severity.WARNING
        assert report.passed

    def test_description_limit(self, book):
        ok = audit_listing(Listing({"title": "X", "description": "d" * 4000}), book)
        assert ok.findings == ()
        report = audit_listing(Listing({"title": "X", "description": "d" * 4001}), book)
        assert rule_ids(report) == ["field_limit.description.max_chars"]
        assert report.findings[0].source.id == "kdp-description"

    def test_kdp_keyword_rules(self, book):
        listing = Listing(
            {
                "title": "The Quiet Harbor",
                "keywords": ["cozy mystery", "free kindle unlimited books", "k" * 51] + ["x"] * 5,
            }
        )
        report = audit_listing(listing, book)
        by_rule = {f.rule_id: f for f in report.findings}
        assert "field_limit.keywords.max_count" in by_rule
        assert by_rule["field_limit.keywords.max_count"].source.status.value == "verified"
        # The 50-char box limit is enforced but cites its unverified source.
        assert by_rule["field_limit.keywords.item.max_chars"].source.status.value == "unverified"
        assert by_rule["keyword_promotional_references"].severity is Severity.ERROR
        assert by_rule["keyword_avoid_terms"].severity is Severity.WARNING
        assert by_rule["keyword_avoid_terms"].observed == ["kindle unlimited", "book"]

    def test_keyword_html_and_quotes(self, book):
        listing = Listing({"title": "X", "keywords": ["<b>cozy</b>", '"small town"']})
        ids = rule_ids(audit_listing(listing, book))
        assert "keyword_html_tags" in ids
        assert "keyword_quotation_marks" in ids

    def test_book_has_no_bullets_field(self, book):
        report = audit_listing(Listing({"title": "X", "bullets": ["a"]}), book)
        assert rule_ids(report) == ["unknown_field.bullets"]
