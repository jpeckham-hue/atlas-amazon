"""Structured-output budgets: tight, but always enough for a valid answer.

"Maximal" answers below use the longest labels, a long entity name and a
25-word rationale of long words. Their size is counted at the conservative
3 characters per token (real JSON/English is closer to 4), and must fit the
configured budget.
"""

import json
import math

import pytest

from atlas_amazon.judgments import ENTITY_LABELS, INTENT_LABELS, JudgmentRequest, JudgmentType
from atlas_amazon.semantic import BatchedJudgmentProvider, ScriptedTransport
from atlas_amazon.semantic.batch import batch_items
from atlas_amazon.semantic.budgets import (
    CONSERVATIVE_CHARS_PER_TOKEN,
    MAX_THEMES,
    RATIONALE_WORDS,
    batch_output_budget,
    item_output_budget,
    single_output_budget,
    themes_output_budget,
)
from atlas_amazon.semantic.prompts import load_template
from atlas_amazon.semantic.tiers import OPUS_STRONG, ModelTiers

LONG_RATIONALE = " ".join(["characterizes"] * RATIONALE_WORDS)  # 25 x 13 letters
LONG_ENTITY = "Supercalifragilistic Brand Company"


def tokens(obj) -> int:
    return math.ceil(len(json.dumps(obj, ensure_ascii=False)) / CONSERVATIVE_CHARS_PER_TOKEN)


def maximal(kind: JudgmentType, *, batched: bool) -> dict:
    item = {"confidence": 0.95, "rationale": LONG_RATIONALE}
    if batched:
        item |= {"id": "ent-0123456789", "type": kind.value}
    if kind is JudgmentType.RELEVANCE:
        item["score"] = 0.85
    elif kind is JudgmentType.INTENT:
        item |= {"label": max(INTENT_LABELS, key=len), "score": 0.85}
    elif kind is JudgmentType.ENTITY:
        item |= {"label": max(ENTITY_LABELS, key=len), "entity": LONG_ENTITY}
    else:
        item["equivalent"] = False
    return item


@pytest.mark.parametrize("kind", list(JudgmentType))
def test_item_budget_fits_a_maximal_valid_item(kind):
    assert tokens(maximal(kind, batched=True)) <= item_output_budget(kind)
    assert tokens(maximal(kind, batched=False)) <= single_output_budget(kind)


@pytest.mark.parametrize("kind", list(JudgmentType))
def test_individual_templates_cover_their_budget(kind):
    template = load_template(kind.value)
    assert single_output_budget(kind) <= template.max_tokens <= 256  # was 4096 in v0.4b


def test_full_batch_of_maximal_items_fits_and_stays_under_the_cap():
    kinds = [JudgmentType.ENTITY] * 40
    body = {"results": [maximal(k, batched=True) for k in kinds]}
    assert tokens(body) <= batch_output_budget(kinds)
    assert batch_output_budget(kinds) <= load_template("judgment_batch").max_tokens
    mixed = [JudgmentType.RELEVANCE, JudgmentType.INTENT, JudgmentType.ENTITY] * 3
    assert batch_output_budget(mixed) < 9 * 200 < 9 * 4096


def test_batches_split_when_the_budget_would_exceed_the_cap():
    requests = [
        JudgmentRequest.about_keyword(JudgmentType.ENTITY, f"keyword {i}", product_title="x")
        for i in range(120)
    ]
    provider = BatchedJudgmentProvider(ScriptedTransport(lambda r: None))
    from atlas_amazon.semantic.batched import BatchSettings

    provider.batching = BatchSettings(max_items=120)
    groups = provider._batches(batch_items(requests))
    cap = provider.template.max_tokens
    assert len(groups) > 1
    assert all(batch_output_budget(i.request.type for i in g) <= cap for g in groups)


def test_thinking_models_reserve_their_allowance():
    kinds = [JudgmentType.RELEVANCE] * 5
    with_thinking = batch_output_budget(kinds, thinking_allowance=OPUS_STRONG.thinking_allowance)
    assert with_thinking == batch_output_budget(kinds) + OPUS_STRONG.thinking_allowance
    assert ModelTiers().fast.thinking_allowance == ModelTiers().strong.thinking_allowance == 0


def test_review_theme_budget_fits_maximal_themes():
    reviews = 20
    themes = [
        {
            "theme": "lid leaks after a few weeks of use",
            "polarity": "negative",
            "review_refs": [f"R{i}" for i in range(1, reviews + 1)][: reviews * 2 // MAX_THEMES],
            "terms": ["leak proof lid", "spill resistant", "secure seal", "no drips"],
            "rationale": LONG_RATIONALE,
        }
        for _ in range(MAX_THEMES)
    ]
    assert tokens({"themes": themes}) <= themes_output_budget(reviews)
    assert themes_output_budget(reviews) <= load_template("review_themes").max_tokens
