"""Batched, tiered judgments: batching, partial failure, escalation, cache, limits, plans.

All offline: scripted transports answer batch requests item by item.
"""

import json
import re

import pytest

from atlas_amazon.judgments import JudgmentRequest, parse_judgment
from atlas_amazon.providers import JudgmentProvider
from atlas_amazon.semantic import (
    BatchedJudgmentProvider,
    BatchSettings,
    EscalationPolicy,
    RecordingTransport,
    ReplayTransport,
    ScriptedTransport,
    SemanticBudget,
    SemanticCache,
    UsageLedger,
    find_secrets,
)
from atlas_amazon.semantic.batch import (
    BATCH_MALFORMED,
    DUPLICATE,
    MALFORMED,
    MISSING,
    OK,
    REFUSAL,
    TYPE_MISMATCH,
    batch_items,
    chunk,
    item_id,
    parse_batch_response,
    render_batch_input,
)
from atlas_amazon.semantic.prompts import load_template
from atlas_amazon.semantic.tiers import FAST, STRONG
from semantic_helpers import reply

TITLE = "Acme Insulated Water Bottle"
KEYWORDS = ["insulated water bottle", "kids water bottle", "straw lid"]
ANSWERS = {
    "relevance": {"score": 0.9, "confidence": 0.9, "rationale": "Names the product type."},
    "intent": {"label": "transactional", "score": 0.8, "confidence": 0.9, "rationale": "Buy."},
    "entity": {"label": "none", "entity": "", "confidence": 0.9, "rationale": "Generic."},
    "equivalence": {"equivalent": True, "confidence": 0.9, "rationale": "Same request."},
}
_INPUT = re.compile(r"<input>\s*(.*?)\s*</input>", re.S)


def kw(kind, keyword):
    return JudgmentRequest.about_keyword(kind, keyword, product_title=TITLE, seeds=["water bottle"])


def keyword_requests(keywords=KEYWORDS):
    return [kw(kind, k) for k in keywords for kind in ("relevance", "intent", "entity")]


def items_of(request):
    return json.loads(_INPUT.search(request["messages"][0]["content"]).group(1))["items"]


def batch_transport(answer=None, mutate=None, stop_reason="end_turn", text=None):
    """Answers every item of a batch request (by id), optionally mutating the result list."""

    def respond(request):
        results = []
        for it in items_of(request):
            subject = it.get("keyword") or " || ".join(it.get("phrases", ()))
            body = (answer(request, it["type"], subject) if answer else None) or ANSWERS[it["type"]]
            results.append({"id": it["id"], "type": it["type"], **body})
        if mutate:
            results = mutate(results, request)
        return reply(
            {"results": results}, model=request["model"], stop_reason=stop_reason, text=text
        )

    return ScriptedTransport(respond)


def provider(transport, **kwargs):
    kwargs.setdefault("escalation", EscalationPolicy.disabled())
    return BatchedJudgmentProvider(transport, **kwargs)


def judge(p, requests=None):
    out = p.judge(requests or keyword_requests(), marketplace="US", run_id="r1")
    return out, [parse_judgment(e) for e in out if e.kind == "judgment"]


def by_subject(judgments):
    return {(j.type.value, j.subject): j for j in judgments}


class TestItemsAndPrompt:
    def test_ids_are_stable_typed_and_order_independent(self):
        reqs = keyword_requests()
        assert item_id(reqs[0]).startswith("rel-") and len(item_id(reqs[0])) == 14
        assert batch_items(reqs) == batch_items(list(reversed(reqs)))
        assert len(batch_items(reqs + reqs)) == len(reqs)  # duplicates collapse
        # A keyword's judgments sit together.
        subjects = [i.request.subject for i in batch_items(reqs)]
        assert subjects == sorted(subjects)

    def test_context_is_hoisted_but_hashes_cover_full_input(self):
        data = render_batch_input(batch_items(keyword_requests()))
        assert list(data["contexts"]) == ["C1"]
        assert all(i["context"] == "C1" for i in data["items"])
        assert data["contexts"]["C1"]["product_title"] == TITLE

    def test_balanced_chunks(self):
        items = batch_items(keyword_requests(KEYWORDS * 1 + ["a b", "c d", "e f", "g h"]))
        sizes = [len(c) for c in chunk(items, 8)]
        assert sum(sizes) == len(items) and max(sizes) - min(sizes) <= 1 and max(sizes) <= 8

    def test_one_request_per_batch_and_schema(self):
        transport = batch_transport()
        judge(provider(transport))
        [req] = transport.requests
        template = load_template("judgment_batch")
        assert req["model"] == FAST.model and "effort" not in req["output_config"]
        assert req["output_config"]["format"]["schema"] == template.schema
        assert req["max_tokens"] < 9 * 200  # computed from the 9 items, not 9 x 4096
        assert not find_secrets(req)


class TestParsing:
    def setup_method(self):
        self.items = batch_items(keyword_requests())

    def body(self, results):
        return json.dumps({"results": results})

    def good(self):
        return [
            {"id": i.id, "type": i.request.type.value, **ANSWERS[i.request.type.value]}
            for i in self.items
        ]

    def test_out_of_order_matched_by_id(self):
        parsed = parse_batch_response(self.items, self.body(self.good()[::-1]), "end_turn")
        assert parsed.out_of_order and parsed.count(OK) == len(self.items)

    def test_missing_duplicate_unknown_mistyped_and_malformed(self):
        results = self.good()
        dropped = results.pop(0)
        results.append(dict(results[0]))  # duplicate of the (new) first
        results.append({"id": "rel-0000000000", "type": "relevance", **ANSWERS["relevance"]})
        results[1] = {
            **results[1],
            "type": "entity" if results[1]["type"] != "entity" else "intent",
        }
        results[2] = {k: v for k, v in results[2].items() if k != "rationale"}
        results.append("not an object")
        parsed = parse_batch_response(self.items, self.body(results), "end_turn")
        statuses = {o.id: o.status for o in parsed.outcomes.values()}
        assert statuses[dropped["id"]] == MISSING
        assert statuses[results[0]["id"]] == DUPLICATE
        assert statuses[results[1]["id"]] == TYPE_MISMATCH
        assert statuses[results[2]["id"]] == MALFORMED
        assert parsed.unknown_ids == ("rel-0000000000",) and parsed.unattributable == 1
        assert parsed.count(OK) == len(self.items) - 4  # siblings unaffected

    @pytest.mark.parametrize(
        ("text", "stop", "status"),
        [
            (None, "refusal", REFUSAL),
            ('{"results": [', "max_tokens", BATCH_MALFORMED),
            ('{"answers": []}', "end_turn", BATCH_MALFORMED),
            ("[]", "end_turn", BATCH_MALFORMED),
        ],
    )
    def test_batch_level_failures(self, text, stop, status):
        parsed = parse_batch_response(self.items, text, stop)
        assert parsed.batch_error == status and parsed.count(status) == len(self.items)


class TestBatchedJudgments:
    def test_contract_and_evidence_per_item(self):
        p = provider(batch_transport())
        assert isinstance(p, JudgmentProvider)
        out, judgments = judge(p)
        [call] = [e for e in out if e.kind == "semantic_call"]
        assert len(judgments) == 9 and len({j.evidence_id for j in judgments}) == 9
        for request in keyword_requests():
            j = by_subject(judgments)[(request.type.value, request.subject)]
            assert j.input_hash == request.input_hash
            assert j.prompt_version == "judgment_batch-v1" and j.model == FAST.model
            assert j.rationale and j.confidence == 0.9
            assert j.call["call_evidence_id"] == call.id and j.call["tier"] == "fast"
            assert j.call["batch"] == {"item_id": item_id(request), "items": 9}
            assert j.call["requested_model"] == FAST.model
        assert list(call.payload["items"]) == [i.id for i in batch_items(keyword_requests())]

    def test_out_of_order_response_gives_identical_judgments(self):
        def content(judgments):
            return {
                (j.type.value, j.subject, j.input_hash, str(j.result), j.confidence, j.rationale)
                for j in judgments
            }

        _, ordered = judge(provider(batch_transport()))
        _, shuffled = judge(provider(batch_transport(mutate=lambda r, q: r[::-1])))
        # Each judgment is the same; only the raw response (call lineage) differs.
        assert content(ordered) == content(shuffled) and len(ordered) == 9

    def test_one_malformed_item_keeps_valid_siblings(self):
        def mutate(results, request):
            results[0] = {**results[0], "confidence": 7}  # out of range
            return results

        p = provider(batch_transport(mutate=mutate))
        _, judgments = judge(p)
        assert len(judgments) == 8
        assert [o for _, o in p.failures] == [MALFORMED]
        [rec] = p.usage.records
        assert rec.outcome == "partial" and rec.judgments == 8 and rec.items == 9
        assert dict(rec.item_failures) == {MALFORMED: 1}

    def test_missing_and_duplicate_results_are_unanswered(self):
        def mutate(results, request):
            return [*results[1:], results[1]]  # first missing, second duplicated

        p = provider(batch_transport(mutate=mutate))
        _, judgments = judge(p)
        assert len(judgments) == 7
        assert sorted(o for _, o in p.failures) == [DUPLICATE, MISSING]
        summary = p.usage.summary("r1")
        assert summary.groups[0].failures == {"item_duplicate": 1, "item_missing": 1}

    def test_batch_level_refusal_produces_no_judgments_but_keeps_the_call(self):
        p = provider(batch_transport(stop_reason="refusal", text=""))
        out, judgments = judge(p)
        assert judgments == [] and [e.kind for e in out] == ["semantic_call"]
        assert p.usage.records[0].outcome == "refusal"
        assert {o for _, o in p.failures} == {REFUSAL}

    def test_max_items_splits_into_balanced_batches(self):
        transport = batch_transport()
        _, judgments = judge(provider(transport, batching=BatchSettings(max_items=4)))
        assert [len(items_of(r)) for r in transport.requests] == [3, 3, 3]
        assert len(judgments) == 9


class TestEscalation:
    def test_low_confidence_escalates_to_strong_and_records_why(self):
        def answer(request, kind, subject):
            if request["model"] == FAST.model and (kind, subject) == ("entity", "straw lid"):
                return {"label": "brand", "entity": "Straw", "confidence": 0.3, "rationale": "?"}
            return None

        transport = batch_transport(answer)
        p = provider(transport, escalation=EscalationPolicy())
        out, judgments = judge(p)
        assert [r["model"] for r in transport.requests] == [FAST.model, STRONG.model]
        assert len(items_of(transport.requests[1])) == 1  # only the flagged item
        strong_req = transport.requests[1]
        assert strong_req["thinking"] == {"type": "between_tools"}
        j = by_subject(judgments)[("entity", "straw lid")]
        assert j.label == "none" and j.model == STRONG.model and j.call["tier"] == "strong"
        esc = j.call["escalation"]
        assert esc["reason"] == "low_confidence" and esc["from_model"] == FAST.model
        assert esc["from_result"] == {"label": "brand", "entity": "Straw"}
        calls = {e.id for e in out if e.kind == "semantic_call"}
        assert esc["from_call_evidence_id"] in calls and j.call["call_evidence_id"] in calls
        assert len(judgments) == 9  # still one judgment per request
        summary = p.usage.summary("r1")
        assert (summary.fast_calls, summary.strong_calls, summary.escalations) == (1, 1, 1)
        assert [e.outcome for e in p.escalation_events] == ["strong_answered"]

    def test_no_escalation_when_confident(self):
        transport = batch_transport()
        p = provider(transport, escalation=EscalationPolicy())
        judge(p)
        assert len(transport.requests) == 1 and p.escalation_events == []

    def test_failed_items_escalate_and_strong_failure_keeps_fast_answer(self):
        def mutate(results, request):
            if request["model"] == FAST.model:
                return results[1:]  # first item missing
            return [{**r, "confidence": 0.95} for r in results]

        transport = batch_transport(mutate=mutate)
        p = provider(transport, escalation=EscalationPolicy())
        _, judgments = judge(p)
        assert len(transport.requests) == 2 and len(judgments) == 9
        assert p.escalation_events[0].reason == "failed"

        def low(request, kind, subject):
            if (kind, subject) == ("relevance", "kids water bottle"):
                return {"score": 0.4, "confidence": 0.2, "rationale": "unsure"}
            return None

        def strong_breaks(results, request):
            return [] if request["model"] == STRONG.model else results

        p = provider(batch_transport(low, mutate=strong_breaks), escalation=EscalationPolicy())
        _, judgments = judge(p)
        j = by_subject(judgments)[("relevance", "kids water bottle")]
        assert j.model == FAST.model and j.confidence == 0.2  # fast answer kept
        assert p.escalation_events[0].outcome == "strong_failed, kept fast answer"

    def test_heuristic_disagreement_and_ambiguous_equivalence(self):
        def answer(request, kind, subject):
            if request["model"] != FAST.model:
                return None
            if (kind, subject) == ("relevance", "straw lid"):
                return {"score": 0.95, "confidence": 0.6, "rationale": "?"}  # heuristic 0.0
            if kind == "equivalence":
                return {"equivalent": True, "confidence": 0.65, "rationale": "maybe"}
            return None

        policy = EscalationPolicy()
        p = provider(batch_transport(answer), escalation=policy)
        reqs = [*keyword_requests(), JudgmentRequest.equivalence("bottle water", "water bottle")]
        judge(p, reqs)
        reasons = sorted(e.reason for e in p.escalation_events)
        assert reasons == ["ambiguous_equivalence", "heuristic_disagreement"]

    def test_escalation_cap_bounds_strong_items(self):
        def answer(request, kind, subject):
            if request["model"] == FAST.model:
                return {**ANSWERS[kind], "confidence": 0.1}
            return None

        transport = batch_transport(answer)
        p = provider(transport, escalation=EscalationPolicy(max_escalations=2))
        _, judgments = judge(p)
        assert len(items_of(transport.requests[1])) == 2
        assert len(judgments) == 9  # the rest keep their (low-confidence) fast answers
        outcomes = [e.outcome for e in p.escalation_events]
        assert outcomes.count("cap_reached") == 7 and outcomes.count("strong_answered") == 2
        plan = p.plans_for("r1")[0]
        assert sum(c.items for c in plan.escalation_reserve) == 2


class TestCacheAndReplay:
    def test_partial_cache_hits_inside_a_batch(self, tmp_path):
        cache = SemanticCache(tmp_path / "cache.jsonl")
        _, first = judge(provider(batch_transport(), cache=cache), keyword_requests(KEYWORDS[:2]))
        transport = batch_transport()
        p = provider(transport, cache=cache)
        plan = p.plan(keyword_requests(), marketplace="US", run_id="r1")
        assert (plan.cache_hits, plan.live, plan.planned_calls) == (6, 3, 1)
        _, second = judge(p)
        [req] = transport.requests
        assert {i["keyword"] for i in items_of(req)} == {"straw lid"}  # only uncached items
        assert {j.evidence_id for j in first} <= {j.evidence_id for j in second}
        assert len(second) == 9
        assert p.usage.summary("r1").cache_hits == 6

    def test_cache_is_per_judgment_not_per_batch(self, tmp_path):
        cache = SemanticCache(tmp_path / "cache.jsonl")
        judge(provider(batch_transport(), cache=cache))
        assert len(cache) == 9  # one entry per judgment; the exchange is stored once
        transport = batch_transport()
        _, again = judge(provider(transport, cache=cache), keyword_requests(KEYWORDS[1:]))
        assert transport.requests == [] and len(again) == 6  # different batch, all hits

    def test_cached_low_confidence_answer_plans_a_certain_escalation(self, tmp_path):
        cache = SemanticCache(tmp_path / "cache.jsonl")

        def low(request, kind, subject):
            return {**ANSWERS[kind], "confidence": 0.2} if kind == "intent" else None

        judge(provider(batch_transport(low), cache=cache))  # escalation disabled
        p = provider(batch_transport(), cache=cache, escalation=EscalationPolicy())
        plan = p.plan(keyword_requests())
        assert plan.live == 0 and len(plan.escalations) == 1 and plan.escalations[0].items == 3
        assert plan.planned_calls == 1 and plan.escalation_reserve == ()

    def test_record_then_replay_batched_is_identical_and_offline(self, tmp_path):
        path = tmp_path / "rec.jsonl"
        out, _ = judge(provider(RecordingTransport(batch_transport(), path)))
        replay = ReplayTransport(path)
        assert len(replay) == 1
        again, _ = judge(provider(replay))
        assert [e.id for e in again] == [e.id for e in out]
        rec = UsageLedger()
        provider(ReplayTransport(path), ledger=rec).judge(
            keyword_requests(KEYWORDS[:1]), marketplace="US", run_id="r1"
        )
        assert rec.records[0].outcome == "replay_miss"  # a different batch is not invented


class TestLimits:
    def test_call_limit_stops_before_the_next_batch(self):
        transport = batch_transport()
        ledger = UsageLedger(budget=SemanticBudget(max_live_calls=1))
        p = provider(transport, ledger=ledger, batching=BatchSettings(max_items=3))
        _, judgments = judge(p)
        assert len(transport.requests) == 1 and len(judgments) == 3
        assert ledger.summary("r1").halts == ("max_live_calls=1 reached",)

    def test_cost_limit_uses_the_tight_batch_budget(self):
        p = provider(batch_transport())
        plan = p.plan(keyword_requests())
        [call] = plan.batches
        # The worst case of the planned batch is priced at its computed max_tokens.
        enough = UsageLedger(budget=SemanticBudget(max_cost_usd=call.worst_case_cost_usd + 1e-4))
        transport = batch_transport()
        judge(provider(transport, ledger=enough))
        assert len(transport.requests) == 1
        short = UsageLedger(budget=SemanticBudget(max_cost_usd=call.worst_case_cost_usd / 2))
        transport = batch_transport()
        out, _ = judge(provider(transport, ledger=short))
        assert transport.requests == [] and out == []
        assert short.records[0].outcome == "budget"


class TestPlan:
    def test_plan_makes_no_calls_and_matches_execution(self):
        transport = batch_transport()
        p = provider(transport, batching=BatchSettings(max_items=4), escalation=EscalationPolicy())
        plan = p.plan(keyword_requests())
        assert transport.requests == []
        assert plan.live == 9 and plan.planned_calls == 3
        assert plan.expected_cost_usd < plan.worst_case_cost_usd
        assert plan.escalation_reserve and plan.worst_case_calls > plan.planned_calls
        judge(p)
        from atlas_amazon.semantic.transport import request_hash

        assert [c.request_hash for c in plan.batches] == [
            request_hash(r) for r in transport.requests
        ]

    def test_run_plan_before_any_live_call(self):
        from atlas_amazon.research import load_scenario
        from atlas_amazon.semantic import LLMReviewThemeProvider
        from atlas_amazon.semantic.plan import render_plan_markdown
        from semantic_helpers import SCENARIOS

        transport = batch_transport()
        ledger = UsageLedger()
        sc = load_scenario(SCENARIOS / "book_cozy_mystery.json").with_providers(
            judgments=BatchedJudgmentProvider(transport, ledger=ledger),
            review_themes=LLMReviewThemeProvider(transport, ledger=ledger),
        )
        from atlas_amazon.evidence import InMemoryEvidenceStore
        from atlas_amazon.research import ResearchRun

        run = ResearchRun(
            product=sc.product,
            listing=sc.listing,
            recipe_id=sc.product.recipe_id,
            run_id=sc.run_id,
            providers=sc.providers,
            store=InMemoryEvidenceStore(),
            started_at=sc.started_at,
        )
        plan = run.plan_semantics()
        assert transport.requests == []  # inspectable before execution
        stages = {s.stage: s for s in plan.stages}
        assert set(stages) == {"review_themes", "equivalence_judgments", "keyword_judgments"}
        kw_stage = stages["keyword_judgments"]
        # Planned on the 14 families before the equivalence merge (13 after): an upper bound.
        assert (kw_stage.requested, kw_stage.human, kw_stage.deterministic) == (42, 2, 1)
        assert kw_stage.live == 39 and plan.planned_calls == 3
        assert any("upper bound" in n for n in plan.notes)
        assert "keyword_judgments" in render_plan_markdown(plan)


def test_evidence_lineage_survives_batching_in_a_run():
    from atlas_amazon.evidence import InMemoryEvidenceStore
    from atlas_amazon.research import load_scenario
    from semantic_helpers import RECORDINGS, SCENARIOS
    from test_semantic_replay import providers

    store = InMemoryEvidenceStore()
    transport = ReplayTransport(RECORDINGS / "physical_water_bottle.jsonl")
    result = (
        load_scenario(SCENARIOS / "physical_water_bottle.json")
        .with_providers(**providers(transport, UsageLedger()))
        .run(store=store)
    )
    model = [j for j in result.judgments if j.provider == "anthropic"]
    assert len(model) == 48
    for j in model:
        call = store.get(j.call["call_evidence_id"])
        assert call.kind == "semantic_call" and call.run_id == result.metadata.run_id
        assert j.call["batch"]["item_id"] in call.payload["items"]
        assert call.payload["request_hash"] == j.call["request_hash"]
        assert (
            f'"id": "{j.call["batch"]["item_id"]}"'
            in call.payload["request"]["messages"][0]["content"]
        )
    [escalated] = [j for j in model if "escalation" in j.call]
    origin = store.get(escalated.call["escalation"]["from_call_evidence_id"])
    assert escalated.call["batch"]["item_id"] in origin.payload["items"]
    assert origin.payload["tier"] == "fast" and escalated.call["tier"] == "strong"
    # The escalated equivalence judgment is the one that links the family.
    kids = result.families.family_of("kids water bottle")
    assert kids.links[0].evidence_ids == (escalated.evidence_id,)
    # Ranking signals cite batched judgment evidence that is in the store.
    d = result.derivation("insulated water bottle")
    [rel_id] = d.signals.relevance.evidence_ids
    assert parse_judgment(store.get(rel_id)).call["tier"] == "fast"
