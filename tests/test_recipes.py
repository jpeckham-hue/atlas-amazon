import math
import textwrap
from datetime import date

import pytest

from atlas_amazon.models import Severity, SourceStatus
from atlas_amazon.recipes import (
    KEYWORD_SIGNALS,
    RecipeError,
    available_recipes,
    load_recipe,
)
from atlas_amazon.recipes.loader import is_official_policy_url
from atlas_amazon.recipes.schema import FIELD_LIMITS

BUILTINS = ["amazon-base", "book", "physical-product"]


def all_limits(recipe):
    """Yield (field, limit name, value, SourceRef) for every limit set in a recipe."""
    for spec in recipe.fields.values():
        for limit in FIELD_LIMITS:
            value = getattr(spec, limit)
            if value is not None:
                yield spec.name, limit, value, spec.source_for(limit)


def test_builtin_recipes_are_discoverable():
    assert available_recipes() == BUILTINS


@pytest.mark.parametrize("rid", BUILTINS)
def test_builtin_recipes_load_and_satisfy_invariants(rid):
    recipe = load_recipe(rid)
    assert recipe.id == rid
    assert recipe.lineage[0] == "amazon-base"
    assert recipe.lineage[-1] == rid
    assert set(recipe.keyword_weights) == set(KEYWORD_SIGNALS)
    assert math.isclose(sum(recipe.keyword_weights.values()), 1.0)
    assert set(recipe.coverage_weights) <= set(recipe.fields)


# ---------------------------------------------------------------------------
# Provenance and traceability


@pytest.mark.parametrize("rid", BUILTINS)
def test_every_limit_and_rule_has_a_dated_source(rid):
    recipe = load_recipe(rid)
    for _field, _limit, _value, source in all_limits(recipe):
        assert source is not None
        assert isinstance(source.as_of, date)
    for rule in recipe.rules.values():
        assert isinstance(rule.source.as_of, date)


@pytest.mark.parametrize("rid", BUILTINS)
def test_source_status_contracts(rid):
    for source in load_recipe(rid).sources.values():
        if source.status is SourceStatus.VERIFIED:
            assert source.url and is_official_policy_url(source.url), source.id
        elif source.status is SourceStatus.UNVERIFIED:
            assert source.note, source.id
        # Third-party references never stand in for the authoritative URL.
        if source.url:
            assert source.url not in source.see_also


# Every rule and limit confirmed in the 2026-10-03 verification pass, pinned to
# the exact official page it was confirmed on. If Amazon changes a page,
# re-verify, then update the recipe AND these tables together.
SC_TITLE = "https://sellercentral.amazon.com/help/hub/reference/external/GYTR6SYGFA5E3EQC"
SC_BULLETS = "https://sellercentral.amazon.com/help/hub/reference/external/GX5L8BF8GLMML6CX"
SC_SEARCH = "https://sellercentral.amazon.com/help/hub/reference/external/GNYWHX2TP7C8GXHK"
KDP_META = "https://kdp.amazon.com/en_US/help/topic/G201097560"
KDP_DESC = "https://kdp.amazon.com/en_US/help/topic/G201189630"
KDP_KW = "https://kdp.amazon.com/en_US/help/topic/G201298500"

VERIFIED_LIMITS = {
    ("physical-product", "title", "max_chars"): (75, SC_TITLE),
    ("physical-product", "item_highlights", "max_chars"): (125, SC_TITLE),
    ("physical-product", "search_terms", "max_bytes"): (249, SC_SEARCH),
    ("book", "description", "max_chars"): (4000, KDP_DESC),
    ("book", "keywords", "max_count"): (7, KDP_KW),
}

VERIFIED_RULES = {
    ("physical-product", "title_word_repetition"): SC_TITLE,
    ("physical-product", "title_disallowed_characters"): SC_TITLE,
    ("physical-product", "title_promotional_phrases"): SC_TITLE,
    ("physical-product", "title_restricted_phrases"): SC_TITLE,
    ("physical-product", "title_subjective_commentary"): SC_TITLE,
    ("physical-product", "bullet_prohibited_claims"): SC_BULLETS,
    ("physical-product", "bullet_guarantee_information"): SC_BULLETS,
    ("physical-product", "bullet_placeholder_text"): SC_BULLETS,
    ("physical-product", "bullet_special_characters"): SC_BULLETS,
    ("physical-product", "backend_repetition"): SC_SEARCH,
    ("physical-product", "backend_prohibited_terms"): SC_SEARCH,
    ("book", "title_subtitle_length"): KDP_META,
    ("book", "title_promotional_references"): KDP_META,
    ("book", "title_html_tags"): KDP_META,
    ("book", "keyword_promotional_references"): KDP_META,
    ("book", "keyword_html_tags"): KDP_META,
    ("book", "keyword_avoid_terms"): KDP_KW,
    ("book", "keyword_quotation_marks"): KDP_KW,
}

# Limits that official documentation does not confirm, kept on purpose.
UNVERIFIED_LIMITS = {
    ("physical-product", "bullets", "max_count"),
    ("physical-product", "bullets", "item_max_chars"),
    ("physical-product", "description", "max_chars"),
    ("book", "keywords", "item_max_chars"),
}


@pytest.mark.parametrize(("key", "expected"), sorted(VERIFIED_LIMITS.items()))
def test_verified_limits_trace_to_official_pages(key, expected):
    rid, field, limit = key
    value, url = expected
    spec = load_recipe(rid).fields[field]
    source = spec.source_for(limit)
    assert getattr(spec, limit) == value
    assert source.status is SourceStatus.VERIFIED
    assert source.url == url
    assert source.as_of == date(2026, 10, 3)


@pytest.mark.parametrize(("key", "url"), sorted(VERIFIED_RULES.items()))
def test_verified_rules_trace_to_official_pages(key, url):
    rid, rule_id = key
    rule = load_recipe(rid).rules[rule_id]
    assert rule.enabled
    assert rule.source.status is SourceStatus.VERIFIED
    assert rule.source.url == url


@pytest.mark.parametrize("rid", BUILTINS)
def test_status_inventory_is_complete(rid):
    """Every limit is either pinned as verified or listed as knowingly unverified."""
    recipe = load_recipe(rid)
    for field, limit, _value, source in all_limits(recipe):
        key = (rid, field, limit)
        if source.status is SourceStatus.VERIFIED:
            assert key in VERIFIED_LIMITS, f"verified limit not pinned: {key}"
        else:
            assert key in UNVERIFIED_LIMITS, f"unverified limit not acknowledged: {key}"
    for rule in recipe.rules.values():
        if rule.source.status is SourceStatus.VERIFIED:
            assert (rid, rule.id) in VERIFIED_RULES, f"verified rule not pinned: {rule.id}"


def test_book_inherits_no_seller_central_product_rules():
    """Seller Central title requirements exempt media (ABIS_BOOK, ABIS_EBOOKS)."""
    recipe = load_recipe("book")
    for rule in recipe.rules.values():
        assert "sellercentral" not in (rule.source.url or ""), rule.id
    for _field, _limit, _value, source in all_limits(recipe):
        assert "sellercentral" not in (source.url or "")
    assert recipe.fields["title"].max_chars is None
    assert recipe.sources["sc-media-product-types"].status is SourceStatus.VERIFIED


def test_amazon_base_sets_no_limits_or_rules():
    recipe = load_recipe("amazon-base")
    assert list(all_limits(recipe)) == []
    assert recipe.rules == {}


def test_physical_product_shape():
    recipe = load_recipe("physical-product")
    assert recipe.lineage == ("amazon-base", "physical-product")
    assert recipe.fields["title"].required  # inherited from amazon-base
    assert recipe.backend.mode == "bytes"
    assert recipe.backend.field_name == "search_terms"
    assert recipe.rules["backend_visible_overlap"].source.status is SourceStatus.HEURISTIC
    assert recipe.rules["title_promotional_extended"].severity is Severity.WARNING
    assert recipe.coverage_weights == {
        "title": 1.0,
        "description": 0.2,
        "item_highlights": 0.7,
        "bullets": 0.6,
        "search_terms": 0.3,
    }


def test_book_shape():
    recipe = load_recipe("book")
    assert "bullets" not in recipe.fields
    assert recipe.backend.mode == "slots"
    assert recipe.rules["title_subtitle_length"].params["max_chars"] == 199
    keywords = recipe.fields["keywords"]
    assert keywords.source.id == "kdp-keywords"
    assert keywords.source_for("item_max_chars").id == "kdp-keyword-box-length-unconfirmed"
    assert keywords.source_for("item_max_chars").see_also  # third-party refs kept apart
    assert recipe.keyword_weights["relevance"] == 0.40


def test_unknown_recipe():
    with pytest.raises(RecipeError, match="not found"):
        load_recipe("nope")
    with pytest.raises(RecipeError, match="invalid recipe id"):
        load_recipe("../etc")


# ---------------------------------------------------------------------------
# Validation against custom recipe directories

BASE = """
id = "{rid}"
version = "1"

[sources.s]
title = "Test source"
as_of = 2026-01-01
status = "heuristic"

[fields.title]
kind = "text"
max_chars = 10
source = "s"

[scoring.keyword]
relevance = 0.2
demand = 0.2
competition = 0.2
intent = 0.2
competitor_coverage = 0.2

[scoring.coverage]
title = 1.0
"""


def write_base(tmp_path, rid="base", extra=""):
    (tmp_path / f"{rid}.toml").write_text(BASE.format(rid=rid) + extra, encoding="utf-8")


def write_child(tmp_path, rid, body, parent="base"):
    """A child recipe, so `body` can override tables the base already defines."""
    head = f'id = "{rid}"\nversion = "1"\nextends = "{parent}"\n'
    (tmp_path / f"{rid}.toml").write_text(head + textwrap.dedent(body), encoding="utf-8")


def test_minimal_custom_recipe_loads(tmp_path):
    write_base(tmp_path, "mini")
    recipe = load_recipe("mini", tmp_path)
    assert recipe.backend is None
    assert recipe.rules == {}


def test_lists_are_replaced_not_concatenated(tmp_path):
    write_base(tmp_path, extra='[research]\npriorities = ["a", "b"]\n')
    write_child(tmp_path, "child", '[research]\npriorities = ["c"]\n')
    assert load_recipe("child", tmp_path).research_priorities == ("c",)


def test_child_tables_merge_key_by_key(tmp_path):
    write_base(tmp_path)
    write_child(tmp_path, "child", "[fields.title]\nmax_chars = 20\n")
    title = load_recipe("child", tmp_path).fields["title"]
    assert title.max_chars == 20
    assert title.kind == "text"
    assert title.source.id == "s"


@pytest.mark.parametrize(
    ("body", "match"),
    [
        ("[fields.title]\nmax_chars = 0\n", "positive integer"),
        ("[fields.bullets]\nkind = 'list'\nmax_count = 5\n", "require a source"),
        ("[fields.x]\nkind = 'text'\nmax_count = 2\nsource = 's'\n", "not valid for a text"),
        ("[fields.x]\nkind = 'blob'\n", "kind"),
        ("[fields.title]\nmaxchars = 5\n", "unknown keys"),
        ("[scoring.keyword]\nrelevance = 0.5\n", "sum to 1"),
        ("[scoring.coverage]\nbogus = 1.0\n", "unknown fields"),
        ("[rules.r]\ncheck = 'magic'\nseverity = 'error'\nsource = 's'\n", "unknown check"),
        (
            "[rules.r]\ncheck = 'prohibited_terms'\nseverity = 'error'\n"
            "fields = ['title']\nterms = ['x']\n",
            "cite a source",
        ),
        (
            "[rules.r]\ncheck = 'prohibited_terms'\nseverity = 'error'\nsource = 's'\n"
            "fields = ['nope']\nterms = ['x']\n",
            "unknown field",
        ),
        (
            "[rules.r]\ncheck = 'prohibited_terms'\nseverity = 'error'\nsource = 's'\n"
            "fields = ['title']\n",
            "required param",
        ),
        (
            "[rules.r]\ncheck = 'word_repetition'\nseverity = 'fatal'\nsource = 's'\n"
            "fields = ['title']\nmax_repeats = 2\n",
            "severity",
        ),
        (
            "[rules.r]\ncheck = 'backend_visible_overlap'\nseverity = 'warning'\nsource = 's'\n"
            "visible_fields = ['title']\n",
            "require a \\[backend\\]",
        ),
        ("[backend]\nfield = 'title'\nmode = 'bytes'\nsource = 's'\n", "max_bytes"),
        ("[sources.t]\ntitle = 'x'\nas_of = '2026-01-01'\nstatus = 'heuristic'\n", "as_of"),
        ("[sources.t]\ntitle = 'x'\nas_of = 2026-01-01\nstatus = 'gospel'\n", "status"),
        ("[surprise]\nx = 1\n", "unknown keys"),
        # Provenance policy
        ("[sources.t]\ntitle = 'x'\nas_of = 2026-01-01\nstatus = 'verified'\n", "official"),
        (
            "[sources.t]\ntitle = 'x'\nas_of = 2026-01-01\nstatus = 'verified'\n"
            "url = 'https://kindlepreneur.com/7-kindle-keywords/'\n",
            "official",
        ),
        (
            "[sources.t]\ntitle = 'x'\nas_of = 2026-01-01\nstatus = 'verified'\n"
            "url = 'https://sellercentral.amazon.com/seller-forums/discussions/t/abc'\n",
            "official",
        ),
        (
            "[sources.t]\ntitle = 'x'\nas_of = 2026-01-01\nstatus = 'verified'\n"
            "url = 'http://kdp.amazon.com/en_US/help/topic/G201097560'\n",
            "official",
        ),
        ("[sources.t]\ntitle = 'x'\nas_of = 2026-01-01\nstatus = 'unverified'\n", "explain why"),
        (
            "[sources.t]\ntitle = 'x'\nas_of = 2026-01-01\nstatus = 'heuristic'\nsee_also = 'u'\n",
            "see_also",
        ),
        # Per-limit sources
        (
            "[fields.title]\nlimit_sources = { max_bytes = 's' }\n",
            "not a limit set on this field",
        ),
        ("[fields.title]\nlimit_sources = { max_chars = 'nope' }\n", "unknown source"),
        (
            "[fields.k]\nkind = 'list'\nmax_count = 7\nitem_max_chars = 50\n"
            "limit_sources = { item_max_chars = 's' }\n",
            "require a source",
        ),
    ],
)
def test_validation_errors(tmp_path, body, match):
    write_base(tmp_path)
    write_child(tmp_path, "bad", body)
    with pytest.raises(RecipeError, match=match):
        load_recipe("bad", tmp_path)


def test_verified_source_with_official_url_loads(tmp_path):
    write_base(
        tmp_path,
        extra=(
            "[sources.v]\ntitle = 'KDP'\nas_of = 2026-10-03\nstatus = 'verified'\n"
            "url = 'https://kdp.amazon.com/en_US/help/topic/G201097560'\n"
            "see_also = ['https://example.com/guide']\nscope = 'KDP'\n"
        ),
    )
    source = load_recipe("base", tmp_path).sources["v"]
    assert source.status is SourceStatus.VERIFIED
    assert source.scope == "KDP"
    assert source.see_also == ("https://example.com/guide",)


def test_limit_sources_override_field_source(tmp_path):
    write_base(
        tmp_path,
        extra=(
            "[sources.u]\ntitle = 'u'\nas_of = 2026-01-01\nstatus = 'unverified'\nnote = 'why'\n"
            "[fields.k]\nkind = 'list'\nmax_count = 7\nitem_max_chars = 50\nsource = 's'\n"
            "limit_sources = { item_max_chars = 'u' }\n"
        ),
    )
    spec = load_recipe("base", tmp_path).fields["k"]
    assert spec.source_for("max_count").id == "s"
    assert spec.source_for("item_max_chars").id == "u"


def test_child_can_partially_override_a_rule(tmp_path):
    write_base(
        tmp_path,
        extra=(
            "[rules.promo]\ncheck = 'prohibited_terms'\nfields = ['title']\nterms = ['x']\n"
            "severity = 'error'\nsource = 's'\n"
        ),
    )
    write_child(tmp_path, "child", "[rules.promo]\nseverity = 'warning'\n")
    rule = load_recipe("child", tmp_path).rules["promo"]
    assert rule.severity is Severity.WARNING
    assert rule.params["terms"] == ["x"]
    write_child(tmp_path, "off", "[rules.promo]\nenabled = false\n")
    assert load_recipe("off", tmp_path).enabled_rules() == ()


def test_id_must_match_filename(tmp_path):
    (tmp_path / "a.toml").write_text('id = "b"\nversion = "1"\n', encoding="utf-8")
    with pytest.raises(RecipeError, match="file name"):
        load_recipe("a", tmp_path)


def test_inheritance_cycle_detected(tmp_path):
    for rid, parent in (("x", "y"), ("y", "x")):
        (tmp_path / f"{rid}.toml").write_text(
            f'id = "{rid}"\nversion = "1"\nextends = "{parent}"\n', encoding="utf-8"
        )
    with pytest.raises(RecipeError, match="cycle"):
        load_recipe("x", tmp_path)


def test_invalid_toml(tmp_path):
    (tmp_path / "broken.toml").write_text("id = \n", encoding="utf-8")
    with pytest.raises(RecipeError, match="invalid TOML"):
        load_recipe("broken", tmp_path)
