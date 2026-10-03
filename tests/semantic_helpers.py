"""Shared helpers for semantic-layer tests (no network, no credentials)."""

import json
from pathlib import Path

from atlas_amazon.judgments import JudgmentRequest, JudgmentType
from atlas_amazon.semantic import ScriptedTransport, TransportResponse
from atlas_amazon.semantic.usage import estimate_tokens

SCENARIOS = Path(__file__).parent / "fixtures" / "scenarios"
RECORDINGS = Path(__file__).parent / "fixtures" / "recordings"
TS = "2026-10-03T12:00:00+00:00"


def reply(
    structured=None,
    *,
    text=None,
    stop_reason="end_turn",
    model="claude-opus-5-5",
    usage=None,
    rid="msg_test",
):
    body = text if text is not None else json.dumps(structured)
    return TransportResponse(
        id=rid,
        model=model,
        stop_reason=stop_reason,
        text=body,
        usage=usage
        if usage is not None
        else {
            "input_tokens": 300,
            "output_tokens": 120,
            "cache_read_input_tokens": 0,
            "cache_creation_input_tokens": 0,
        },
        responded_at=TS,
        transport="anthropic",
    )


def constant(structured=None, **kwargs):
    """A ScriptedTransport that always returns the same reply."""
    return ScriptedTransport(lambda request: reply(structured, **kwargs))


def relevance(keyword="insulated water bottle", title="Acme Insulated Water Bottle"):
    return JudgmentRequest.about_keyword(
        JudgmentType.RELEVANCE, keyword, product_title=title, seeds=["water bottle"]
    )


def estimate(request):
    return estimate_tokens(request)
