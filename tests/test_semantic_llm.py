"""LLM judgment and review-theme providers via scripted, recording and replay transports."""

import json
from datetime import UTC, datetime

import pytest

from atlas_amazon.evidence import make_evidence
from atlas_amazon.jsonvalue import thaw
from atlas_amazon.judgments import JudgmentRequest, JudgmentType, parse_judgment
from atlas_amazon.providers import JudgmentProvider, ReviewThemeProvider
from atlas_amazon.reviews import parse_review_theme
from atlas_amazon.semantic import (
    AnthropicTransport,
    LiveCallsDisabled,
    LLMJudgmentProvider,
    LLMReviewThemeProvider,
    LLMSettings,
    RecordingTransport,
    ReplayTransport,
    ScriptedTransport,
    SemanticBudget,
    SemanticCache,
    UsageLedger,
    find_secrets,
    load_template,
)
from atlas_amazon.semantic.tiers import DIRECT_OPUS_STRONG, FAST, STRONG
from semantic_helpers import TS, constant, relevance, reply

GOOD = {"score": 0.9, "confidence": 0.8, "rationale": "Names the product type and attribute."}


def judge(transport, requests=None, **kwargs):
    provider = LLMJudgmentProvider(transport, **kwargs)
    out = provider.judge(requests or [relevance()], marketplace="US", run_id="r1")
    return provider, out


def judgments_in(evidence):
    return [parse_judgment(e) for e in evidence if e.kind == "judgment"]


class TestRequests:
    def test_default_request_is_the_fast_tier(self):
        transport = constant(GOOD)
        judge(transport)
        [req] = transport.requests
        template = load_template("relevance")
        assert req["model"] == FAST.model == "anthropic/claude-haiku-4.5"
        assert req["providerOptions"] == {"gateway": {"only": ["anthropic"]}}  # routing pinned
        assert req["max_tokens"] == template.max_tokens == 256
        assert req["system"] == template.system
        # Haiku 4.5 rejects `effort`; it is omitted, not defaulted.
        assert req["output_config"] == {
            "format": {"type": "json_schema", "schema": template.schema},
        }
        assert "betas" not in req and "fallbacks" not in req
        assert "thinking" not in req and "temperature" not in req
        assert '"keyword": "insulated water bottle"' in req["messages"][0]["content"]

    def test_opus_settings_add_effort_fallbacks_and_thinking_allowance(self):
        transport = constant(GOOD)
        judge(transport, settings=DIRECT_OPUS_STRONG)
        [req] = transport.requests
        template = load_template("relevance")
        assert req["model"] == "claude-opus-5-5" and "providerOptions" not in req
        assert req["max_tokens"] == template.max_tokens + DIRECT_OPUS_STRONG.thinking_allowance
        assert req["output_config"]["effort"] == "low"
        assert req["betas"] == ["server-side-fallback-2026-07-01"]
        assert req["fallbacks"] == "default"

    def test_strong_tier_disables_extended_thinking_without_fallbacks(self):
        transport = constant(GOOD)
        judge(transport, settings=STRONG)
        [req] = transport.requests
        assert req["model"] == STRONG.model == "anthropic/claude-sonnet-5.5"
        assert req["thinking"] == {"type": "between_tools"}
        assert req["output_config"]["effort"] == "low"
        assert "fallbacks" not in req
        with pytest.raises(ValueError, match="between_tools"):
            LLMSettings(
                "claude-sonnet-5-5", thinking={"type": "between_tools"}, refusal_fallbacks=True
            )

    def test_settings(self):
        transport = constant(GOOD)
        judge(
            transport,
            settings=LLMSettings(
                model="claude-sonnet-5-5", effort="medium", refusal_fallbacks=False
            ),
        )
        [req] = transport.requests
        assert req["model"] == "claude-sonnet-5-5" and req["output_config"]["effort"] == "medium"
        assert "betas" not in req and "fallbacks" not in req
        with pytest.raises(ValueError):
            LLMSettings(effort="extreme")


class TestValidatedJudgments:
    def test_happy_path_evidence_contract(self):
        provider, out = judge(constant(GOOD, model="claude-opus-5-5"))
        assert isinstance(provider, JudgmentProvider)
        call, evidence = out
        assert call.kind == "semantic_call" and evidence.kind == "judgment"
        j = parse_judgment(evidence)
        assert (j.score, j.confidence, j.rationale) == (0.9, 0.8, GOOD["rationale"])
        assert j.model == "claude-opus-5-5" and j.provider == "anthropic"
        assert j.prompt_version == "relevance-v3"
        assert j.input_hash == relevance().input_hash
        assert j.judged_at == datetime.fromisoformat(TS)
        assert j.call["call_evidence_id"] == call.id
        assert j.call["usage"]["input_tokens"] == 300
        assert j.call["requested_model"] == FAST.model  # served != requested
        # The original request and response are preserved for audit and replay.
        assert call.payload["request"]["system"] == load_template("relevance").system
        assert json.loads(call.payload["response"]["text"]) == GOOD
        assert call.payload["prompt"]["fingerprint"] == load_template("relevance").fingerprint
        assert not find_secrets(call.payload) and not find_secrets(evidence.payload)

    def test_fallback_served_model_is_recorded(self):
        _, out = judge(constant(GOOD, model="claude-opus-4-8"), settings=DIRECT_OPUS_STRONG)
        j = judgments_in(out)[0]
        assert j.model == "claude-opus-4-8"
        assert j.call["requested_model"] == "claude-opus-5-5"

    @pytest.mark.parametrize(
        ("kind", "structured"),
        [
            (
                JudgmentType.INTENT,
                {
                    "label": "transactional",
                    "score": 0.8,
                    "confidence": 0.7,
                    "rationale": "ready to buy",
                },
            ),
            (
                JudgmentType.ENTITY,
                {
                    "label": "brand",
                    "entity": "Hydra",
                    "confidence": 0.9,
                    "rationale": "competitor brand",
                },
            ),
            (
                JudgmentType.ENTITY,
                {"label": "none", "entity": "", "confidence": 0.9, "rationale": "generic"},
            ),
        ],
    )
    def test_other_types(self, kind, structured):
        request = JudgmentRequest.about_keyword(kind, "hydra bottle", product_title="Acme")
        _, out = judge(constant(structured), [request])
        [j] = judgments_in(out)
        assert j.type is kind
        if kind is JudgmentType.ENTITY and structured["entity"] == "":
            assert j.result["entity"] is None

    def test_equivalence(self):
        request = JudgmentRequest.equivalence("water bottle", "bottle water")
        _, out = judge(
            constant({"equivalent": False, "confidence": 0.95, "rationale": "drink"}), [request]
        )
        assert judgments_in(out)[0].result == {"equivalent": False}

    def test_duplicate_requests_call_once(self):
        transport = constant(GOOD)
        judge(transport, [relevance(), relevance()])
        assert len(transport.requests) == 1


class TestMalformedResponses:
    @pytest.mark.parametrize(
        ("kwargs", "outcome"),
        [
            ({"text": "not json"}, "malformed"),
            ({"text": "[1, 2]"}, "malformed"),
            ({"text": ""}, "malformed"),
            ({"text": '{"score": 0.9, "confidence": 0.8, "rationale": "x"'}, "malformed"),
            ({"structured": {"score": 1.7, "confidence": 0.8, "rationale": "x"}}, "malformed"),
            ({"structured": {"score": 0.5, "confidence": 3, "rationale": "x"}}, "malformed"),
            ({"structured": {"score": 0.5, "confidence": 0.5, "rationale": " "}}, "malformed"),
            ({"structured": {"score": 0.5, "rationale": "x"}}, "malformed"),
            (
                {"structured": {"score": 0.5, "confidence": 0.5, "rationale": "x", "extra": 1}},
                "malformed",
            ),
            ({"structured": GOOD, "stop_reason": "refusal"}, "refusal"),
        ],
    )
    def test_no_judgment_and_failure_recorded(self, kwargs, outcome):
        structured = kwargs.pop("structured", None)
        provider, out = judge(constant(structured, **kwargs))
        assert judgments_in(out) == []
        assert [e.kind for e in out] == ["semantic_call"]  # exchange still kept for audit
        [record] = provider.usage.records
        assert record.outcome == outcome and record.source == "live"
        assert provider.failures and provider.failures[0][1] == outcome

    def test_wrong_label_rejected(self):
        request = JudgmentRequest.about_keyword(JudgmentType.INTENT, "mug", product_title="A")
        _, out = judge(
            constant({"label": "buying", "score": 0.5, "confidence": 0.5, "rationale": "x"}),
            [request],
        )
        assert judgments_in(out) == []

    def test_transport_errors_are_contained(self):
        def boom(request):
            raise RuntimeError("network down")

        provider, out = judge(ScriptedTransport(boom), [relevance("a b"), relevance("c d")])
        assert out == []
        assert [r.outcome for r in provider.usage.records] == ["error", "error"]


class TestCacheAndReplay:
    def test_cache_hit_skips_transport_and_reproduces_evidence(self, tmp_path):
        cache = SemanticCache(tmp_path / "cache.jsonl")
        first_transport = constant(GOOD)
        _, first = judge(first_transport, cache=cache)
        second_transport = constant({"score": 0.1, "confidence": 0.1, "rationale": "different"})
        provider2, second = judge(second_transport, cache=SemanticCache(tmp_path / "cache.jsonl"))
        assert second_transport.requests == []  # served from the persistent cache
        assert [e.id for e in second] == [e.id for e in first]  # identical evidence
        assert provider2.usage.records[0].source == "cache"
        assert provider2.usage.records[0].estimated_cost_usd == 0.0

    def test_invalid_results_are_not_cached(self, tmp_path):
        cache = SemanticCache(tmp_path / "cache.jsonl")
        judge(constant(text="nope"), cache=cache)
        assert len(cache) == 0

    def test_stale_cache_entry_after_template_edit(self, tmp_path, monkeypatch):
        cache = SemanticCache(tmp_path / "cache.jsonl")
        judge(constant(GOOD), cache=cache)
        provider = LLMJudgmentProvider(constant(GOOD), cache=cache)
        edited = provider.templates["relevance"]
        from dataclasses import replace

        provider.templates["relevance"] = replace(edited, user=edited.user + "\nBe brief.")
        transport = provider._caller.transport
        provider.judge([relevance()], marketplace="US", run_id="r1")
        assert len(transport.requests) == 1  # fingerprint mismatch -> miss -> new call

    def test_mismatched_prompt_version_or_model_misses(self, tmp_path):
        cache = SemanticCache(tmp_path / "cache.jsonl")
        judge(constant(GOOD), cache=cache)
        other_model = constant(GOOD)
        judge(other_model, cache=cache, settings=LLMSettings(model="claude-sonnet-5-5"))
        assert len(other_model.requests) == 1
        provider = LLMJudgmentProvider(constant(GOOD), cache=cache)
        from dataclasses import replace

        t = provider.templates["relevance"]
        provider.templates["relevance"] = replace(t, version="relevance-v9")
        provider.judge([relevance()], marketplace="US", run_id="r1")
        assert len(provider._caller.transport.requests) == 1

    def test_record_then_replay_is_identical_and_offline(self, tmp_path):
        path = tmp_path / "rec.jsonl"
        _, live = judge(RecordingTransport(constant(GOOD), path))
        replay = ReplayTransport(path)
        provider, replayed = judge(replay)
        assert [e.id for e in replayed] == [e.id for e in live]
        assert provider.usage.records[0].source == "replay"
        assert provider.usage.summary("r1").live_calls == 0

    def test_replay_miss_is_unanswered_not_invented(self, tmp_path):
        path = tmp_path / "rec.jsonl"
        judge(RecordingTransport(constant(GOOD), path))
        provider, out = judge(ReplayTransport(path), [relevance("totally different")])
        assert out == []
        assert provider.usage.records[0].outcome == "replay_miss"

    def test_tampered_recording_rejected(self, tmp_path):
        path = tmp_path / "rec.jsonl"
        judge(RecordingTransport(constant(GOOD), path))
        text = path.read_text(encoding="utf-8").replace("insulated water bottle", "other")
        path.write_text(text, encoding="utf-8")
        with pytest.raises(Exception, match="checksum"):
            ReplayTransport(path)


class TestLiveSafety:
    def test_live_transport_disabled_without_flag(self):
        transport = AnthropicTransport()
        with pytest.raises(LiveCallsDisabled):
            transport.send({"model": "m"})
        provider, out = judge(transport)
        assert out == [] and provider.usage.records == []  # stopped before any call

    def test_live_transport_with_injected_client(self):
        class Block:
            type, text = "text", json.dumps(GOOD)

        class Usage:
            input_tokens, output_tokens = 321, 45
            cache_read_input_tokens = cache_creation_input_tokens = 0

        class Message:
            id, model, stop_reason, content, usage = (
                "msg_1",
                "claude-opus-5-5",
                "end_turn",
                [Block()],
                Usage(),
            )

        class Endpoint:
            def __init__(self):
                self.calls = []

            def create(self, **params):
                self.calls.append(params)
                return Message()

        class Client:
            def __init__(self):
                self.messages, self.beta = Endpoint(), type("B", (), {})()
                self.beta.messages = Endpoint()

        client = Client()
        transport = AnthropicTransport(
            client=client, allow_live=True, clock=lambda: datetime(2026, 10, 3, tzinfo=UTC)
        )
        provider, out = judge(transport, settings=DIRECT_OPUS_STRONG)
        assert len(client.beta.messages.calls) == 1  # fallbacks use the beta endpoint
        assert judgments_in(out)[0].call["usage"]["input_tokens"] == 321
        rec = provider.usage.records[0]
        assert rec.source == "live" and rec.estimated_cost_usd == pytest.approx(
            (321 * 4 + 45 * 20) / 1_000_000
        )

    def test_call_limit_stops_batch_before_next_call(self):
        transport = constant(GOOD)
        ledger = UsageLedger(budget=SemanticBudget(max_live_calls=2))
        _, out = judge(transport, [relevance(f"kw {i}") for i in range(5)], ledger=ledger)
        assert len(transport.requests) == 2
        assert len(judgments_in(out)) == 2
        assert ledger.summary("r1").halts == ("max_live_calls=2 reached",)
        assert [r.outcome for r in ledger.records][-1] == "budget"

    def test_cost_limit_stops_before_overspending(self):
        # Haiku: each call costs $0.0007; the worst case for the next call is
        # ~$0.0015 (full 256-token output), so calls stop with headroom left.
        transport = constant(
            GOOD, model="claude-haiku-4-5", usage={"input_tokens": 200, "output_tokens": 100}
        )
        ledger = UsageLedger(budget=SemanticBudget(max_cost_usd=0.005))
        judge(transport, [relevance(f"kw {i}") for i in range(10)], ledger=ledger)
        spent = ledger.summary("r1").estimated_cost_usd
        assert spent <= 0.005
        assert 0 < len(transport.requests) < 10
        assert "max_cost_usd" in ledger.summary("r1").halts[0]

    def test_budget_below_one_worst_case_call_blocks_all_calls(self):
        transport = constant(GOOD)
        ledger = UsageLedger(budget=SemanticBudget(max_cost_usd=0.001))
        _, out = judge(transport, ledger=ledger)
        assert transport.requests == [] and out == []

    def test_replay_and_cache_do_not_count_as_live_calls(self, tmp_path):
        path = tmp_path / "rec.jsonl"
        judge(RecordingTransport(constant(GOOD), path))
        ledger = UsageLedger(budget=SemanticBudget(max_live_calls=0))
        _, out = judge(ReplayTransport(path), ledger=ledger)
        assert judgments_in(out)  # replay allowed even with zero live calls


def review(asin, index, text):
    return make_evidence(
        provider="fx",
        kind="review_sample",
        marketplace="US",
        retrieved_at=datetime(2026, 10, 3, tzinfo=UTC),
        payload={"asin": asin, "index": index, "rating": 3, "text": text},
        subject=asin,
        run_id="r1",
    )


REVIEWS = [
    review("B0C0000001", 0, "Lid leaks."),
    review("B0C0000002", 0, "Leaked in bag."),
    review("B0OWN00001", 0, "Love it"),
]


class TestReviewThemes:
    def refs(self, transport):
        content = transport.requests[0]["messages"][0]["content"]
        data = json.loads(content.split("<input>")[1].split("</input>")[0])
        return {r["text"]: r["ref"] for r in data["reviews"]}

    def run(self, themes_for):
        holder = {}

        def respond(request):
            data = json.loads(
                request["messages"][0]["content"].split("<input>")[1].split("</input>")[0]
            )
            holder["refs"] = {r["text"]: r["ref"] for r in data["reviews"]}
            return reply({"themes": themes_for(holder["refs"])})

        transport = ScriptedTransport(respond)
        provider = LLMReviewThemeProvider(transport)
        out = provider.themes(REVIEWS, marketplace="US", run_id="r1")
        return provider, transport, out

    def test_validated_themes_with_recomputed_counts(self):
        provider, _transport, out = self.run(
            lambda refs: [
                {
                    "theme": "lid leaks",
                    "polarity": "negative",
                    "count": 99,  # ignored
                    "review_refs": [refs["Lid leaks."], refs["Leaked in bag."], "R99"],
                    "terms": ["leak proof"],
                    "rationale": "Two reviews mention leaks.",
                }
            ]
        )
        assert isinstance(provider, ReviewThemeProvider)
        call, theme = out
        assert call.kind == "semantic_call"
        parsed = parse_review_theme(theme, {r.id: r for r in REVIEWS})
        assert parsed.count == 2  # recomputed from cited reviews, not the model's 99
        assert parsed.products == ("B0C0000001", "B0C0000002")
        assert parsed.extractor == "claude-opus-5-5"
        assert parsed.extractor_version == "review_themes-v2"
        assert any("R99" in d for d in provider.dropped)

    def test_prompt_contains_only_reviews(self):
        _, transport, _ = self.run(lambda refs: [])
        content = transport.requests[0]["messages"][0]["content"]
        data = json.loads(content.split("<input>")[1].split("</input>")[0])
        assert set(data) == {"reviews"}
        assert all(set(r) == {"ref", "asin", "rating", "text"} for r in data["reviews"])

    def test_themes_without_valid_support_are_dropped(self):
        provider, _, out = self.run(
            lambda refs: [
                {
                    "theme": "invented",
                    "polarity": "positive",
                    "review_refs": ["R42"],
                    "terms": [],
                    "rationale": "x",
                },
                {
                    "theme": "bad polarity",
                    "polarity": "ecstatic",
                    "review_refs": [refs["Love it"]],
                    "terms": [],
                    "rationale": "x",
                },
            ]
        )
        assert [e.kind for e in out] == ["semantic_call"]
        assert any("'invented'" in d for d in provider.dropped)
        assert any("'bad polarity'" in d for d in provider.dropped)

    def test_malformed_and_empty(self):
        provider = LLMReviewThemeProvider(constant(text="{}"))
        assert [e.kind for e in provider.themes(REVIEWS, marketplace="US", run_id="r1")] == [
            "semantic_call"
        ]
        assert provider.usage.records[0].outcome == "malformed"
        assert LLMReviewThemeProvider(constant({"themes": []})).themes([], marketplace="US") == []


class TestGatewayTransport:
    """Vercel AI Gateway is the default live transport. No network here."""

    class FakeAnthropic:
        """Stands in for the `anthropic` module; records client construction."""

        def __init__(self):
            self.kwargs = None

        def Anthropic(self, **kwargs):
            self.kwargs = kwargs
            return object()

    def test_default_live_transport_is_the_gateway(self):
        from atlas_amazon.semantic import GatewayTransport, default_live_transport

        transport = default_live_transport(allow_live=False)
        assert isinstance(transport, GatewayTransport) and transport.is_live
        assert transport.name == "vercel-ai-gateway"
        with pytest.raises(LiveCallsDisabled):
            transport.send({"model": FAST.model})

    def test_gateway_key_is_used_never_anthropic_key(self, monkeypatch):
        from atlas_amazon.semantic import GatewayTransport
        from atlas_amazon.semantic.transport import TransportError

        monkeypatch.delenv("AI_GATEWAY_API_KEY", raising=False)
        monkeypatch.delenv("VERCEL_OIDC_TOKEN", raising=False)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "direct-fake")
        fake = self.FakeAnthropic()
        with pytest.raises(TransportError, match="AI_GATEWAY_API_KEY"):
            GatewayTransport()._make_client(fake)
        monkeypatch.setenv("VERCEL_OIDC_TOKEN", "oidc-fake")
        GatewayTransport()._make_client(fake)
        assert fake.kwargs["api_key"] == "oidc-fake"
        monkeypatch.setenv("AI_GATEWAY_API_KEY", "gw-fake")  # preferred
        transport = GatewayTransport()
        transport._make_client(fake)
        assert fake.kwargs == {
            "api_key": "gw-fake",
            "base_url": "https://ai-gateway.vercel.sh",
            "timeout": 120.0,  # a stalled request fails fast instead of after 10 minutes
            "max_retries": 1,
        }
        assert "gw-fake" not in repr(vars(transport))  # never kept

    def test_gateway_sends_routing_as_body_field_and_records_its_name(self):
        from atlas_amazon.semantic import GatewayTransport

        class Block:
            type, text = "text", json.dumps(GOOD)

        class Message:
            id, model, stop_reason, content, usage = (
                "msg_gw",
                FAST.model,
                "end_turn",
                [Block()],
                None,
            )

        class Endpoint:
            def __init__(self):
                self.calls = []

            def create(self, **params):
                self.calls.append(params)
                return Message()

        class Client:
            def __init__(self):
                self.messages = Endpoint()

        client = Client()
        transport = GatewayTransport(
            client=client, allow_live=True, clock=lambda: datetime(2026, 10, 4, tzinfo=UTC)
        )
        _, out = judge(transport)
        [params] = client.messages.calls
        assert "providerOptions" not in params
        assert params["extra_body"] == {"providerOptions": {"gateway": {"only": ["anthropic"]}}}
        [call] = [e for e in out if e.kind == "semantic_call"]
        assert call.payload["response"]["transport"] == "vercel-ai-gateway"
        assert thaw(call.payload["request"]["providerOptions"]) == {
            "gateway": {"only": ["anthropic"]}
        }
        j = judgments_in(out)[0]
        assert j.model == "anthropic/claude-haiku-4.5"  # served model, provider-qualified

    def test_direct_transport_refuses_gateway_routing(self):
        from atlas_amazon.semantic.transport import TransportError

        transport = AnthropicTransport(client=object(), allow_live=True)
        with pytest.raises(TransportError, match="GatewayTransport"):
            transport.send({"model": "claude-haiku-4-5", "providerOptions": {}})

    def test_gateway_models_are_priced(self):
        from atlas_amazon.semantic import PricingTable

        table = PricingTable()
        assert table.get("anthropic/claude-haiku-4.5") == table.get("claude-haiku-4-5")
        assert table.get("anthropic/claude-sonnet-5.5") == table.get("claude-sonnet-5-5")
        assert table.get("anthropic/claude-opus-5.5") == table.get("claude-opus-5-5")
