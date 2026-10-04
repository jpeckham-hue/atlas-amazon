"""Structured-output token budgets.

v0.4b gave every one-line judgment 4,096 output tokens. Cost guards price
each call at its full `max_tokens`, so that allowance made the worst case
roughly 30x the expected cost. Budgets are now derived from the response
schema, per judgment type, and summed over a batch:

    item budget  = tokens(longest valid item with an empty rationale)
                   + RATIONALE_TOKENS (+ ENTITY_TOKENS for entity items)
    batch budget = BATCH_OVERHEAD + sum(item budgets) + model thinking allowance

Token counts here are deliberately conservative: `CONSERVATIVE_CHARS_PER_TOKEN`
is 3, while JSON with English text usually runs 3.5-4.5 chars per token. The
prompt asks for rationales of at most `RATIONALE_WORDS` words (~33 tokens
typically); `RATIONALE_TOKENS` is 130, enough for 25 thirteen-letter words
counted at 3 chars per token, so even an unusually wordy answer fits. Slack
here only raises the *worst-case* price; actual spend is the tokens written.
`tests/test_semantic_budgets.py` checks that maximal valid answers fit.

Expected (not worst-case) output is estimated with `expected_item_output`,
used only by the call planner's *expected* cost.
"""

from __future__ import annotations

import math
from collections.abc import Iterable

from atlas_amazon.jsonvalue import canonical_json
from atlas_amazon.judgments.contract import ENTITY_LABELS, INTENT_LABELS, JudgmentType

CONSERVATIVE_CHARS_PER_TOKEN = 3
TYPICAL_CHARS_PER_TOKEN = 4
RATIONALE_WORDS = 25  # instructed maximum, stated in every prompt
RATIONALE_TOKENS = 130  # budget per rationale (~4x a typical 25-word sentence)
TYPICAL_RATIONALE_TOKENS = 30
ENTITY_TOKENS = 20  # budget for the entity name itself
BATCH_OVERHEAD = 24  # {"results": [ ... ]} and separators
SINGLE_OVERHEAD = 8
ITEM_ID_LENGTH = 14  # "rel-" + 10 hex characters (see batch.item_id)

# Review themes: a theme is a short label, polarity, refs, up to 4 terms and a
# one-sentence rationale. The prompt caps the number of themes.
MAX_THEMES = 8
THEME_TOKENS = 180  # one theme without its review refs
REF_TOKENS = 4  # one '"R12",' reference
THEMES_OVERHEAD = 24


def _longest_label(labels: Iterable[str]) -> str:
    return max(labels, key=len)


def _skeleton(kind: JudgmentType, *, batched: bool) -> dict:
    """The longest valid item of `kind`, with an empty rationale."""
    item: dict = {"confidence": 0.123, "rationale": ""}
    if batched:
        item |= {"id": "x" * ITEM_ID_LENGTH, "type": kind.value}
    if kind is JudgmentType.RELEVANCE:
        item["score"] = 0.123
    elif kind is JudgmentType.INTENT:
        item |= {"label": _longest_label(INTENT_LABELS), "score": 0.123}
    elif kind is JudgmentType.ENTITY:
        item |= {"label": _longest_label(ENTITY_LABELS), "entity": ""}
    else:
        item["equivalent"] = False
    return item


def _tokens(text: str, chars_per_token: int) -> int:
    return math.ceil(len(text) / chars_per_token)


def item_output_budget(kind: JudgmentType | str, *, batched: bool = True) -> int:
    kind = JudgmentType(kind)
    skeleton = canonical_json(_skeleton(kind, batched=batched))
    extra = ENTITY_TOKENS if kind is JudgmentType.ENTITY else 0
    return _tokens(skeleton, CONSERVATIVE_CHARS_PER_TOKEN) + RATIONALE_TOKENS + extra


def expected_item_output(kind: JudgmentType | str, *, batched: bool = True) -> int:
    kind = JudgmentType(kind)
    skeleton = canonical_json(_skeleton(kind, batched=batched))
    extra = 4 if kind is JudgmentType.ENTITY else 0
    return _tokens(skeleton, TYPICAL_CHARS_PER_TOKEN) + TYPICAL_RATIONALE_TOKENS + extra


def batch_output_budget(kinds: Iterable[JudgmentType | str], *, thinking_allowance: int = 0) -> int:
    return BATCH_OVERHEAD + sum(item_output_budget(k) for k in kinds) + thinking_allowance


def single_output_budget(kind: JudgmentType | str, *, thinking_allowance: int = 0) -> int:
    return SINGLE_OVERHEAD + item_output_budget(kind, batched=False) + thinking_allowance


def themes_output_budget(review_count: int, *, thinking_allowance: int = 0) -> int:
    """Up to MAX_THEMES themes; every review may be cited by up to two themes."""
    return (
        THEMES_OVERHEAD
        + MAX_THEMES * THEME_TOKENS
        + 2 * max(0, review_count) * REF_TOKENS
        + thinking_allowance
    )


def expected_themes_output(review_count: int) -> int:
    themes = min(MAX_THEMES, max(1, review_count // 3))
    return THEMES_OVERHEAD + themes * (THEME_TOKENS // 2) + review_count * REF_TOKENS
