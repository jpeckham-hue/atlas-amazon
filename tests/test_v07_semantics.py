"""v0.7: first-party product context, cache invalidation, strong-tier comparison mode."""

import json
import re

import pytest

from atlas_amazon.evidence import InMemoryEvidenceStore
from atlas_amazon.jsonvalue import thaw
from atlas_amazon.judgments import JudgmentRequest, JudgmentType
from atlas_amazon.judgments.context import MAX_DESCRIPTION_CHARS, product_context
from atlas_amazon.models import Listing, ProductInput
from atlas_amazon.recipes import load_recipe
from atlas_amazon.research import ResearchConfig, ResearchRun, load_scenario
from atlas_amazon.semantic import (
    BatchedJudgmentProvider,
    EscalationPolicy,
    SemanticCache,
    UsageLedger,
)
from atlas_amazon.semantic.cache import CacheKey
from atlas_amazon.semantic.comparison import (
    STRONG_EVAL_PROVIDER,
    evaluate_tier_comparison,
    run_strong_comparison,
)
from atlas_amazon.semantic.tiers import FAST, STRONG
from semantic_helpers import SCENARIOS
from test_semantic_batch import batch_transport, items_of, judge


def scenario(name):
    return load_scenario(SCENARIOS / f"{name}.json")


def keyword_contexts(result):
    return {
        json.dumps(thaw(j.input["context"]), sort_keys=True)
        for j in result.judgments
        if j.type is not JudgmentType.EQUIVALENCE
    }


class TestProductContext:
    def test_physical_product_gets_features_brand_and_description(self):
        sc = scenario("physical_water_bottle")
        ctx = product_context(sc.product, sc.listing, load_recipe("physical-product"), ["s"])
        assert ctx == {
            "product_title": "Acme Insulated Water Bottle 32 oz",
            "seeds": ["s"],
            "category": "physical-product",
            "brand": "Acme",
            "features": [
                "Leak proof lid with carry loop",
                "Double wall vacuum insulation keeps drinks cold for 24 hours",
                "Fits most cup holders",
            ],
            "description": "A sturdy stainless steel bottle for everyday hydration.",
        }

    def test_book_gets_only_supplied_first_party_metadata(self):
        sc = scenario("book_cozy_mystery")
        ctx = product_context(sc.product, sc.listing, load_recipe("book"), ["cozy mystery"])
        assert ctx["subtitle"] == "A Cozy Mystery" and ctx["category"] == "book"
        assert ctx["features"] == [
            "Clean read with no gore or profanity",
            "Includes original bakery recipes",
        ]
        assert "bakery owner Nell Avery" in ctx["description"]
        assert "brand" not in ctx and "author" not in ctx  # not supplied, not invented

    def test_competitor_data_never_enters_the_context(self):
        result = scenario("physical_water_bottle").run()
        words = set(re.findall(r"[a-z]+", " ".join(keyword_contexts(result)).lower()))
        assert "hydra" not in words  # a competitor brand from catalog evidence
        assert all("competitor" not in c for c in keyword_contexts(result))

    def test_bullets_fallback_truncation_and_omitted_empties(self):
        recipe = load_recipe("physical-product")
        long = ("word " * 200).strip()
        listing = Listing({"title": "T", "bullets": ["One", "Two", "One"], "description": long})
        ctx = product_context(ProductInput(title="T", recipe_id=recipe.id), listing, recipe, [])
        assert ctx["features"] == ["One", "Two"]  # listing bullets, deduplicated
        assert ctx["description_truncated"] is True
        assert len(ctx["description"]) <= MAX_DESCRIPTION_CHARS
        bare = product_context(
            ProductInput(title="T", recipe_id=recipe.id), Listing({"title": "T"}), recipe, ["x"]
        )
        assert bare == {"product_title": "T", "seeds": ["x"], "category": "physical-product"}

    def test_run_requests_carry_one_shared_context(self):
        result = scenario("physical_water_bottle").run()
        [ctx] = keyword_contexts(result)
        assert "Leak proof lid with carry loop" in ctx


class TestHashesAndCache:
    def test_context_changes_the_input_hash(self):
        old = JudgmentRequest.about_keyword(
            JudgmentType.RELEVANCE, "leak proof", product_title="T", seeds=["s"]
        )
        new = JudgmentRequest.about_keyword(
            JudgmentType.RELEVANCE,
            "leak proof",
            context={"product_title": "T", "seeds": ["s"], "features": ["Leak proof lid"]},
        )
        assert old.subject == new.subject and old.input_hash != new.input_hash
        with pytest.raises(ValueError):
            JudgmentRequest.about_keyword(JudgmentType.RELEVANCE, "x", context={"seeds": []})

    def test_v06_context_is_still_available(self):
        sc = scenario("physical_water_bottle")
        legacy = sc.run(config=ResearchConfig(product_context=False))
        [ctx] = keyword_contexts(legacy)
        assert set(json.loads(ctx)) == {"product_title", "seeds"}
        assert keyword_contexts(legacy) != keyword_contexts(sc.run())

    def test_old_cache_entries_miss_after_the_context_change(self, tmp_path):
        cache = SemanticCache(tmp_path / "cache.jsonl")
        old = [
            JudgmentRequest.about_keyword(k, "leak proof", product_title="T", seeds=["s"])
            for k in (JudgmentType.RELEVANCE, JudgmentType.INTENT)
        ]
        judge(BatchedJudgmentProvider(batch_transport(), cache=cache), old)
        new = [
            JudgmentRequest.about_keyword(
                r.type,
                "leak proof",
                context={"product_title": "T", "seeds": ["s"], "features": ["Leak proof lid"]},
            )
            for r in old
        ]
        p = BatchedJudgmentProvider(batch_transport(), cache=cache)
        assert p.plan(old).cache_hits == 2  # unchanged requests still hit
        plan = p.plan(new)
        assert (plan.cache_hits, plan.live) == (0, 2)  # new input hashes: automatic miss

    def test_old_prompt_version_entries_miss(self, tmp_path):
        cache = SemanticCache(tmp_path / "cache.jsonl")
        p = BatchedJudgmentProvider(batch_transport(), cache=cache)
        [request] = [JudgmentRequest.about_keyword(JudgmentType.RELEVANCE, "x", product_title="T")]
        stale = CacheKey("relevance", request.input_hash, p.name, FAST.model, "judgment_batch-v1")
        cache.put_exchange(
            "sha256:old", {"tier": "fast", "items": [], "request": {}, "response": {}}
        )
        cache.put(stale, "old-fingerprint", {"structured": {}, "exchange": "sha256:old"})
        assert p.template.version == "judgment_batch-v2"
        assert p.plan([request]).cache_hits == 0


class TestStrongComparison:
    def requests(self):
        ctx = {
            "product_title": "Acme Insulated Water Bottle",
            "seeds": ["water bottle"],
            "features": ["Leak proof lid"],
        }
        return [
            JudgmentRequest.about_keyword(k, kw, context=ctx)
            for kw in ("leak proof", "water bottle")
            for k in (JudgmentType.RELEVANCE, JudgmentType.INTENT, JudgmentType.ENTITY)
        ]

    def test_strong_only_mode_asks_every_item_of_the_strong_tier(self):
        transport = batch_transport()
        p = BatchedJudgmentProvider(transport, evaluation="strong_only")
        assert p.evaluation_only and p.escalation.can_escalate is False
        _, judgments = judge(p, self.requests())
        assert [r["model"] for r in transport.requests] == [STRONG.model]
        assert len(items_of(transport.requests[0])) == 6
        assert {j.call["tier"] for j in judgments} == {"strong"}
        with pytest.raises(ValueError):
            BatchedJudgmentProvider(transport, evaluation="everything")

    def test_comparison_preserves_both_answers_and_never_overwrites(self):
        def answer(request, kind, subject):
            if kind == "intent":
                label = (
                    "transactional"
                    if request["model"] == FAST.model
                    else "commercial_investigation"
                )
                return {"label": label, "score": 0.6, "confidence": 0.9, "rationale": "x"}
            return None

        transport = batch_transport(answer)
        ledger = UsageLedger()
        production_provider = BatchedJudgmentProvider(
            transport, ledger=ledger, escalation=EscalationPolicy.disabled()
        )
        _, production = judge(production_provider, self.requests())
        comparison = run_strong_comparison(
            transport, production, marketplace="US", run_id="r1", ledger=ledger
        )
        assert len(comparison.production) == len(comparison.strong) == 6
        assert {j.provider for j in comparison.strong} == {STRONG_EVAL_PROVIDER}
        assert {j.model for j in comparison.strong} == {STRONG.model}
        assert {j.model for j in comparison.production} == {FAST.model}
        prod_intent = {j.label for j in comparison.production if j.type is JudgmentType.INTENT}
        strong_intent = {j.label for j in comparison.strong if j.type is JudgmentType.INTENT}
        assert prod_intent == {"transactional"} and strong_intent == {"commercial_investigation"}
        assert production == list(comparison.production)  # untouched
        summary = ledger.summary("r1")
        assert (summary.fast_calls, summary.strong_calls) == (1, 1)

        reference = list(comparison.strong)  # pretend the strong answers are the reference
        report = evaluate_tier_comparison(comparison, reference, reference_label="ref")
        intent = {t.type.value: t for t in report.production.by_type}["intent"]
        assert intent.agreed == 0
        assert {t.type.value: t for t in report.strong.by_type}["intent"].agreed == 2
        assert report.head_to_head.by_type[1].agreed == 0

    def test_evaluation_provider_cannot_serve_a_research_run(self):
        sc = scenario("physical_water_bottle")
        evaluator = BatchedJudgmentProvider(batch_transport(), evaluation="strong_only")
        with pytest.raises(ValueError, match="evaluation-only"):
            ResearchRun(
                product=sc.product,
                listing=sc.listing,
                recipe_id=sc.product.recipe_id,
                run_id=sc.run_id,
                providers=sc.with_providers(judgments=evaluator).providers,
                store=InMemoryEvidenceStore(),
                started_at=sc.started_at,
            )


class TestDeterministicBehaviorUnchanged:
    @pytest.mark.parametrize("name", ["book_cozy_mystery", "physical_water_bottle"])
    def test_context_does_not_change_deterministic_outputs(self, name):
        """Fixture judgments are keyed by keyword, so only request inputs differ."""
        sc = scenario(name)
        rich, legacy = sc.run(), sc.run(config=ResearchConfig(product_context=False))
        assert [(s.keyword, s.score) for s in rich.ranked] == [
            (s.keyword, s.score) for s in legacy.ranked
        ]
        assert [f.phrases for f in rich.families.families] == [
            f.phrases for f in legacy.families.families
        ]
        assert [(f.keyword, f.label) for f in rich.entity_flags] == [
            (f.keyword, f.label) for f in legacy.entity_flags
        ]
        assert [str(p.value) for p in rich.proposals] == [str(p.value) for p in legacy.proposals]
        assert rich.audit == legacy.audit
