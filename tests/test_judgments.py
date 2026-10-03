from dataclasses import replace
from datetime import UTC, datetime

import pytest

from atlas_amazon.evidence import decode_record, encode_record, make_evidence
from atlas_amazon.judgments import (
    JudgmentError,
    JudgmentRequest,
    JudgmentType,
    judgment_evidence,
    parse_judgment,
)
from atlas_amazon.providers import FixtureData, FixtureJudgmentProvider, JudgmentProvider

T = datetime(2026, 10, 3, 8, 0, tzinfo=UTC)


def relevance_request(keyword="Insulated Water Bottle"):
    return JudgmentRequest.about_keyword(
        JudgmentType.RELEVANCE, keyword, product_title="Acme Bottle", seeds=["water bottle"]
    )


def make(request=None, result=None, **overrides):
    fields = dict(
        provider="fx",
        request=request or relevance_request(),
        result=result or {"score": 0.8},
        confidence=0.9,
        model="judge-1",
        prompt_version="rel-v1",
        rationale="Matches the product.",
        marketplace="US",
        judged_at=T,
        run_id="r1",
    )
    fields.update(overrides)
    return judgment_evidence(**fields)


class TestRequest:
    def test_normalizes_and_hashes_inputs(self):
        r = relevance_request()
        assert r.input["keyword"] == "insulated water bottle"
        assert r.subject == "insulated water bottle"
        assert r.input_hash.startswith("sha256:") and len(r.input_hash) == 71
        assert r.input_hash == relevance_request("insulated  water bottle").input_hash
        other = JudgmentRequest.about_keyword(
            JudgmentType.RELEVANCE, "insulated water bottle", product_title="Other", seeds=[]
        )
        assert other.input_hash != r.input_hash  # context is part of the input

    def test_equivalence_is_order_independent(self):
        a = JudgmentRequest.equivalence("Water Bottle", "bottle water")
        b = JudgmentRequest.equivalence("bottle water", "water bottle")
        assert a == b and a.subject == "bottle water || water bottle"

    @pytest.mark.parametrize(
        "data",
        [
            {"keyword": ""},
            {"keyword": "x", "context": "nope"},
            {"keyword": "x", "context": {}, "extra": 1},
        ],
    )
    def test_invalid_keyword_input(self, data):
        with pytest.raises(JudgmentError):
            JudgmentRequest(JudgmentType.INTENT, data)

    @pytest.mark.parametrize("phrases", [["b", "a"], ["a", "a"], ["a"], ["a", ""]])
    def test_invalid_equivalence_input(self, phrases):
        with pytest.raises(JudgmentError):
            JudgmentRequest(JudgmentType.EQUIVALENCE, {"phrases": phrases})

    def test_about_keyword_rejects_equivalence(self):
        with pytest.raises(JudgmentError):
            JudgmentRequest.about_keyword(JudgmentType.EQUIVALENCE, "x", product_title="t")


class TestEvidence:
    def test_contract_fields_present_and_round_trip(self):
        ev = make()
        assert ev.kind == "judgment" and ev.subject == "insulated water bottle"
        assert set(ev.payload) == {
            "judgment_type",
            "input",
            "input_hash",
            "result",
            "confidence",
            "model",
            "prompt_version",
            "rationale",
        }
        j = parse_judgment(decode_record(encode_record(ev)))
        assert (j.type, j.score, j.confidence, j.model, j.prompt_version) == (
            JudgmentType.RELEVANCE,
            0.8,
            0.9,
            "judge-1",
            "rel-v1",
        )
        assert j.judged_at == T and j.provider == "fx" and j.rationale

    @pytest.mark.parametrize(
        ("kind", "result"),
        [
            (JudgmentType.INTENT, {"label": "transactional", "score": 0.7}),
            (JudgmentType.ENTITY, {"label": "brand", "entity": "Hydra"}),
            (JudgmentType.ENTITY, {"label": "none", "entity": None}),
        ],
    )
    def test_valid_result_schemas(self, kind, result):
        request = JudgmentRequest.about_keyword(kind, "kw", product_title="t")
        assert parse_judgment(make(request=request, result=result)).result == result

    @pytest.mark.parametrize(
        ("kind", "result"),
        [
            (JudgmentType.RELEVANCE, {"score": 1.5}),
            (JudgmentType.RELEVANCE, {"score": 0.5, "extra": 1}),
            (JudgmentType.INTENT, {"label": "buying", "score": 0.5}),
            (JudgmentType.ENTITY, {"label": "person", "entity": "x"}),
            (JudgmentType.EQUIVALENCE, {"equivalent": "yes"}),
        ],
    )
    def test_invalid_results_rejected_at_creation(self, kind, result):
        request = (
            JudgmentRequest.equivalence("a b", "b a")
            if kind is JudgmentType.EQUIVALENCE
            else JudgmentRequest.about_keyword(kind, "kw", product_title="t")
        )
        with pytest.raises(JudgmentError):
            make(request=request, result=result)

    @pytest.mark.parametrize(
        "overrides",
        [
            {"confidence": 1.2},
            {"rationale": " "},
            {"model": ""},
            {"prompt_version": ""},
        ],
    )
    def test_required_audit_fields(self, overrides):
        with pytest.raises(JudgmentError):
            make(**overrides)

    def test_confidence_may_be_null(self):
        assert parse_judgment(make(confidence=None)).confidence is None


class TestParseDetectsTampering:
    def _forge(self, ev, **payload_changes):
        payload = {**ev.payload, **payload_changes}
        return make_evidence(
            provider=ev.provider,
            kind=ev.kind,
            marketplace=ev.marketplace,
            retrieved_at=ev.retrieved_at,
            payload=payload,
            subject=ev.subject,
            run_id=ev.run_id,
        )

    def test_input_hash_must_match_input(self):
        ev = make()
        forged = self._forge(ev, input={**ev.payload["input"], "keyword": "other"})
        with pytest.raises(JudgmentError, match="input_hash"):
            parse_judgment(forged)

    def test_subject_must_match_input(self):
        ev = replace(make(), subject="something else")
        with pytest.raises(JudgmentError, match="subject"):
            parse_judgment(ev)

    def test_other_problems(self):
        ev = make()
        with pytest.raises(JudgmentError):
            parse_judgment(self._forge(ev, judgment_type="vibes"))
        with pytest.raises(JudgmentError):
            parse_judgment(self._forge(ev, result={"score": 9}))
        with pytest.raises(JudgmentError, match="keys"):
            parse_judgment(self._forge(ev, extra=True))
        with pytest.raises(JudgmentError, match="expected judgment"):
            parse_judgment(
                make_evidence(
                    provider="p",
                    kind="keyword_metric",
                    marketplace="US",
                    retrieved_at=T,
                    payload={},
                )
            )


class TestFixtureProvider:
    FIXTURE = FixtureData.from_dict(
        {
            "provider": "fx",
            "retrieved_at": "2026-10-03T08:00:00+00:00",
            "judgments": {
                "model": "fixture-judge-1",
                "prompt_versions": {"relevance": "rel-v1"},
                "markets": {
                    "US": {
                        "relevance": {
                            "insulated water bottle": {
                                "score": 0.9,
                                "confidence": 0.8,
                                "rationale": "core product",
                            }
                        },
                        "equivalence": {
                            "bottle water || water bottle": {
                                "equivalent": False,
                                "confidence": 0.95,
                                "rationale": "different things",
                            }
                        },
                        "intent": {"broken": {"label": "transactional", "score": 0.5}},
                    }
                },
            },
        }
    )

    def test_satisfies_protocol_and_answers_known_requests(self):
        provider = FixtureJudgmentProvider(self.FIXTURE)
        assert isinstance(provider, JudgmentProvider)
        requests = [
            relevance_request(),
            relevance_request(),  # duplicate request
            relevance_request("unknown keyword"),
            JudgmentRequest.equivalence("water bottle", "bottle water"),
        ]
        out = provider.judge(requests, marketplace="US", run_id="r1")
        assert len(out) == 2  # duplicate collapsed, unknown unanswered
        rel, eq = (parse_judgment(e) for e in out)
        assert rel.score == 0.9 and rel.prompt_version == "rel-v1"
        assert rel.model == "fixture-judge-1"
        assert eq.result == {"equivalent": False}
        assert eq.prompt_version == "fixture-v1"  # default when not configured
        assert out[0].source_url.startswith("fixture://inline#judgments/US/relevance/")
        assert provider.judge(requests, marketplace="US", run_id="r1") == out  # deterministic

    def test_missing_rationale_is_a_fixture_error(self):
        from atlas_amazon.providers import FixtureError

        request = JudgmentRequest.about_keyword(JudgmentType.INTENT, "broken", product_title="t")
        with pytest.raises(FixtureError, match="rationale"):
            FixtureJudgmentProvider(self.FIXTURE).judge([request], marketplace="US")

    def test_other_marketplace_or_no_block(self):
        assert (
            FixtureJudgmentProvider(self.FIXTURE).judge([relevance_request()], marketplace="UK")
            == []
        )
        empty = FixtureData.from_dict(
            {"provider": "fx", "retrieved_at": "2026-10-03T08:00:00+00:00"}
        )
        assert FixtureJudgmentProvider(empty).judge([relevance_request()], marketplace="US") == []
