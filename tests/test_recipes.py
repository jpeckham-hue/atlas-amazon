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

BUILTINS = ["amazon-base", "book", "physical-product"]


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
    # Provenance: every rule and every limited field has a dated source.
    for rule in recipe.rules.values():
        assert isinstance(rule.source.as_of, date)
    for spec in recipe.fields.values():
        has_limit = any(
            getattr(spec, k) is not None
            for k in ("max_chars", "max_bytes", "max_count", "item_max_chars")
        )
        if has_limit:
            assert spec.source is not None


def test_no_builtin_source_claims_verified_yet():
    # Nothing has been re-checked against a primary source yet. Flip a source
    # to verified only after checking it, and update this test when you do.
    for rid in BUILTINS:
        for source in load_recipe(rid).sources.values():
            assert source.status in (SourceStatus.UNVERIFIED, SourceStatus.HEURISTIC)


def test_physical_product_inherits_and_extends_base():
    recipe = load_recipe("physical-product")
    assert recipe.lineage == ("amazon-base", "physical-product")
    assert recipe.fields["title"].max_chars == 200
    assert recipe.fields["search_terms"].max_bytes == 250
    assert recipe.backend is not None
    assert recipe.backend.mode == "bytes"
    assert recipe.backend.field_name == "search_terms"
    # Partial rule override: fields widened, terms/severity inherited.
    promo = recipe.rules["promotional_terms"]
    assert promo.fields == ("title", "bullets")
    assert "free shipping" in promo.params["terms"]
    assert promo.severity is Severity.ERROR
    # Coverage weights merged across the chain.
    assert recipe.coverage_weights == {
        "title": 1.0,
        "description": 0.2,
        "bullets": 0.6,
        "search_terms": 0.3,
    }


def test_book_overrides_base():
    recipe = load_recipe("book")
    assert "bullets" not in recipe.fields
    assert recipe.fields["description"].max_chars == 4000
    assert recipe.fields["description"].source.id == "kdp-metadata-guidelines"
    assert recipe.backend.mode == "slots"
    assert recipe.fields["keywords"].max_count == 7
    assert recipe.fields["keywords"].item_max_chars == 50
    enabled = {r.id for r in recipe.enabled_rules()}
    assert "title_word_repetition" not in enabled
    assert "title_disallowed_characters" not in enabled
    assert {"promotional_terms", "kdp_keyword_terms", "title_subtitle_length"} <= enabled
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
            "[rules.r]\ncheck = 'backend_redundancy'\nseverity = 'warning'\nsource = 's'\n"
            "visible_fields = ['title']\n",
            "requires a \\[backend\\]",
        ),
        ("[backend]\nfield = 'title'\nmode = 'bytes'\nsource = 's'\n", "max_bytes"),
        ("[sources.t]\ntitle = 'x'\nas_of = '2026-01-01'\nstatus = 'heuristic'\n", "as_of"),
        ("[sources.t]\ntitle = 'x'\nas_of = 2026-01-01\nstatus = 'gospel'\n", "status"),
        ("[surprise]\nx = 1\n", "unknown keys"),
    ],
)
def test_validation_errors(tmp_path, body, match):
    write_base(tmp_path)
    write_child(tmp_path, "bad", body)
    with pytest.raises(RecipeError, match=match):
        load_recipe("bad", tmp_path)


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
