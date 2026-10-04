"""Deterministic judgments, recipe known entities, routing and pricing details."""

from pathlib import Path

import pytest

from atlas_amazon.judgments import JudgmentRequest, JudgmentType, parse_judgment
from atlas_amazon.recipes import load_recipe
from atlas_amazon.recipes.loader import RecipeError
from atlas_amazon.research import ResearchConfig, load_scenario
from atlas_amazon.semantic import PricingTable, RuleJudgmentProvider
from atlas_amazon.semantic.benchmark import compare_downstream
from conftest import T0
from semantic_helpers import SCENARIOS


def entity(keyword, title="Acme Insulated Water Bottle 32 oz"):
    return JudgmentRequest.about_keyword(JudgmentType.ENTITY, keyword, product_title=title)


@pytest.fixture
def rules():
    return RuleJudgmentProvider(load_recipe("book"), judged_at=T0)


class TestRules:
    def test_recipe_known_entity(self, rules):
        [ev] = rules.judge(
            [entity("cozy mystery kindle unlimited", "The Quiet Harbor")],
            marketplace="US",
            run_id="r1",
        )
        j = parse_judgment(ev)
        assert (j.label, j.result["entity"]) == ("trademark", "kindle unlimited")
        assert j.provider == "rules" and j.model == "rules:recipe_known_entity"
        assert j.prompt_version == "deterministic-v1" and j.confidence == 1.0
        assert "KDP Help" in j.rationale  # cites the recipe source

    def test_own_title_words_are_not_entities(self):
        rules = RuleJudgmentProvider(load_recipe("physical-product"), judged_at=T0)
        answered = {
            parse_judgment(e).subject
            for e in rules.judge(
                [
                    entity("water bottle"),
                    entity("insulated water bottles 32 oz"),  # plural, number, unit
                    entity("bottle water"),  # same words: still no entity
                    entity("hydra water bottle"),  # 'hydra' is not in the title
                    entity("straw lid"),
                ],
                marketplace="US",
            )
        }
        assert answered == {"water bottle", "insulated water bottles 32 oz", "bottle water"}

    def test_only_entity_requests_are_answered(self, rules):
        reqs = [
            JudgmentRequest.about_keyword(k, "kindle unlimited", product_title="x")
            for k in (JudgmentType.RELEVANCE, JudgmentType.INTENT)
        ] + [JudgmentRequest.equivalence("a b", "b a")]
        assert rules.judge(reqs, marketplace="US") == []

    def test_judged_at_must_be_aware(self):
        from datetime import datetime

        with pytest.raises(ValueError):
            RuleJudgmentProvider(load_recipe("book"), judged_at=datetime(2026, 1, 1))


class TestRecipeEntities:
    def test_book_lists_program_names_with_a_source(self):
        recipe = load_recipe("book")
        assert recipe.known_entities == {"trademark": ("kindle unlimited", "kdp select")}
        assert recipe.known_entities_source.status.value == "verified"
        assert load_recipe("physical-product").known_entities == {}

    def test_invalid_entities_tables_are_rejected(self, tmp_path):
        base = (Path(load_recipe.__code__.co_filename).parent / "data" / "book.toml").read_text(
            encoding="utf-8"
        )
        for bad in ('ghost = ["x"]', 'trademark = [""]', ""):
            text = base.replace('trademark = ["kindle unlimited", "kdp select"]', bad)
            (tmp_path / "book.toml").write_text(text, encoding="utf-8")
            with pytest.raises(RecipeError):
                load_recipe("book", tmp_path)


class TestRouting:
    def test_rules_and_skipping_can_be_turned_off(self):
        sc = load_scenario(SCENARIOS / "physical_water_bottle.json")
        on = sc.run()
        off = sc.run(
            config=ResearchConfig(deterministic_judgments=False, skip_unrankable_judgments=False)
        )
        task_on = next(t for t in on.semantic_tasks if t.task == "keyword_judgments")
        task_off = next(t for t in off.semantic_tasks if t.task == "keyword_judgments")
        assert "5 deterministic" in task_on.note and "6 not needed" in task_on.note
        assert "57 requested" in task_off.note and "deterministic" not in task_off.note
        assert [s.keyword for s in on.ranked] == [s.keyword for s in off.ranked]
        assert [(f.keyword, f.label) for f in on.entity_flags] == [
            (f.keyword, f.label) for f in off.entity_flags
        ]

    @pytest.mark.parametrize("name", ["book_cozy_mystery", "physical_water_bottle"])
    def test_identical_downstream_behavior_individual_vs_batched(self, name):
        identical, differences = compare_downstream(SCENARIOS / f"{name}.json")
        assert identical, differences


def test_pricing_resolves_dated_snapshot_ids():
    table = PricingTable()
    assert table.get("claude-haiku-4-5-20251001") == table.get("claude-haiku-4-5")
    assert table.get("claude-unknown-1") is None
