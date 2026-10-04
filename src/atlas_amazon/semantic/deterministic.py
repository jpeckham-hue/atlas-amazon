"""Deterministic judgments: questions plain code answers without a model.

`RuleJudgmentProvider` is a `JudgmentProvider` that answers only what it can
answer with certainty, and leaves everything else to the model. Its answers
are ordinary judgment Evidence (`provider = "rules"`,
`model = "rules:<rule>"`, `prompt_version = "deterministic-v1"`,
confidence 1.0) with a rationale naming the rule. They pass the same
validation as model judgments and are reported as judgments, not
heuristics: they are exact, not estimates.

Rules (entity judgments only):

* `recipe_known_entity`: the keyword contains a term the recipe lists under
  `[entities]` (for example KDP program names as `trademark`). The label
  comes from the recipe, which cites its source.
* `own_title_words`: every content word of the keyword (ignoring
  connecting words, numbers and units) appears in the seller's own product
  title from the request context. The entity prompt itself says title words
  belong to the seller and are not another company's entity, so the answer
  is `none` by definition.

Relevance and intent are not answered here: no rule reproduces them
reliably. Equivalence is already settled deterministically before a request
is made (`keywords.families`: stopword variants and attribute rotations),
and only the remaining ambiguous pairs reach the model.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from atlas_amazon.judgments.contract import JudgmentRequest, JudgmentType, judgment_evidence
from atlas_amazon.keywords.candidates import EDGE_STOPWORDS
from atlas_amazon.keywords.coverage import contains_phrase
from atlas_amazon.keywords.families import UNIT_WORDS
from atlas_amazon.keywords.normalize import fold_plural, keyword_key, tokenize
from atlas_amazon.models import Evidence
from atlas_amazon.recipes.schema import Recipe

RULES_PROVIDER = "rules"
RULES_VERSION = "deterministic-v1"


class RuleJudgmentProvider:
    name = RULES_PROVIDER

    def __init__(self, recipe: Recipe, *, judged_at: datetime) -> None:
        if judged_at.utcoffset() is None:
            raise ValueError("judged_at must be timezone-aware")
        self.recipe = recipe
        self.judged_at = judged_at
        self._known = [
            (label, term, keyword_key(term))
            for label, terms in sorted(recipe.known_entities.items())
            for term in terms
        ]

    def answer(self, request: JudgmentRequest) -> tuple[str, dict, str] | None:
        """(rule, result, rationale) when a rule settles the request, else None."""
        if request.type is not JudgmentType.ENTITY:
            return None
        keyword = request.input["keyword"]
        key = keyword_key(keyword)
        for label, term, term_key in self._known:
            if contains_phrase(key, term_key):
                source = self.recipe.known_entities_source
                cite = f" ({source.title}, as of {source.as_of})" if source else ""
                return (
                    "recipe_known_entity",
                    {"label": label, "entity": term},
                    f"'{term}' is listed as a {label} in recipe '{self.recipe.id}'{cite}.",
                )
        content = [
            fold_plural(t)
            for t in tokenize(keyword)
            if t not in EDGE_STOPWORDS and not t.isdigit() and t not in UNIT_WORDS
        ]
        title = request.input["context"].get("product_title", "")
        title_words = {fold_plural(t) for t in tokenize(str(title))}
        if content and all(t in title_words for t in content):
            return (
                "own_title_words",
                {"label": "none", "entity": None},
                "Every content word appears in the seller's own product title, so the "
                "keyword names no other company's entity.",
            )
        return None

    def judge(
        self, requests: Sequence[JudgmentRequest], *, marketplace: str, run_id: str | None = None
    ) -> list[Evidence]:
        out, seen = [], set()
        for request in requests:
            if request.input_hash in seen:
                continue
            seen.add(request.input_hash)
            found = self.answer(request)
            if found is None:
                continue
            rule, result, rationale = found
            out.append(
                judgment_evidence(
                    provider=RULES_PROVIDER,
                    request=request,
                    result=result,
                    confidence=1.0,
                    model=f"rules:{rule}",
                    prompt_version=RULES_VERSION,
                    rationale=rationale,
                    marketplace=marketplace,
                    judged_at=self.judged_at,
                    run_id=run_id,
                )
            )
        return out
