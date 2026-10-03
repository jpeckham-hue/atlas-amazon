"""Synthetic (scripted) model responses for offline tests and demo recordings.

**Nothing here is model output.** `fixture_responder` answers semantic
requests deterministically from a scenario's fixture judgments and review
themes, with optional scripted deviations, so the full live code path
(prompt rendering, structured output, validation, recording, replay, cache,
evaluation) can be exercised without network access or credentials.
Responses are marked `synthetic=True`, use the model name
`synthetic-scripted-v1`, and report *estimated* token counts. Real
agreement and cost numbers need a recording made with a live model.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from typing import Any

from atlas_amazon.jsonvalue import canonical_json, thaw
from atlas_amazon.judgments.contract import EQUIVALENCE_SEPARATOR, JudgmentType
from atlas_amazon.providers.fixtures import FixtureData
from atlas_amazon.semantic.prompts import REVIEW_THEMES, TEMPLATE_NAMES, load_template
from atlas_amazon.semantic.transport import TransportResponse
from atlas_amazon.semantic.usage import estimate_tokens

SYNTHETIC_MODEL = "synthetic-scripted-v1"
SYNTHETIC_TIME = "2026-10-03T12:00:00+00:00"
_INPUT = re.compile(r"<input>\s*(.*?)\s*</input>", re.S)

_DEFAULTS = {
    JudgmentType.RELEVANCE.value: {"score": 0.5},
    JudgmentType.INTENT.value: {"label": "commercial_investigation", "score": 0.5},
    JudgmentType.ENTITY.value: {"label": "none", "entity": ""},
    JudgmentType.EQUIVALENCE.value: {"equivalent": False},
}


def _template_name(request: Mapping[str, Any]) -> str:
    for name in TEMPLATE_NAMES:
        if load_template(name).system == request.get("system"):
            return name
    raise ValueError("request does not match any prompt template")


def _input(request: Mapping[str, Any]) -> dict[str, Any]:
    content = request["messages"][0]["content"]
    match = _INPUT.search(content)
    if not match:
        raise ValueError("request has no <input> block")
    return json.loads(match.group(1))


def fixture_responder(
    fixture: FixtureData,
    *,
    marketplace: str = "US",
    deviations: Mapping[tuple[str, str], Mapping[str, Any]] | None = None,
):
    """A responder for `ScriptedTransport` driven by fixture judgments and themes.

    `deviations` maps (judgment type, subject) to a full answer (result fields plus
    confidence and rationale) that replaces the fixture answer, to simulate
    model disagreement.
    """
    deviations = dict(deviations or {})
    judgments = thaw(fixture.semantic.get("judgments", {}).get("markets", {}).get(marketplace, {}))
    themes = thaw(fixture.semantic.get("review_themes", {}).get("markets", {}).get(marketplace, []))
    reviews = thaw(fixture.sections["reviews"].get(marketplace, {}))

    def respond(request: Mapping[str, Any]) -> TransportResponse:
        name = _template_name(request)
        data = _input(request)
        if name == REVIEW_THEMES:
            ref_of = {(r["asin"], r["text"]): r["ref"] for r in data["reviews"]}
            out = []
            for theme in themes:
                refs = []
                for item in theme.get("reviews", ()):
                    asin, index = item.split("/")
                    texts = reviews.get(asin, [])
                    if int(index) < len(texts):
                        ref = ref_of.get((asin, texts[int(index)]["text"]))
                        if ref:
                            refs.append(ref)
                if refs:
                    out.append(
                        {
                            "theme": theme["theme"],
                            "polarity": theme["polarity"],
                            "review_refs": refs,
                            "terms": theme.get("terms", []),
                            "rationale": theme.get("rationale", "scripted theme"),
                        }
                    )
            structured: dict[str, Any] = {"themes": out}
        else:
            subject = (
                EQUIVALENCE_SEPARATOR.join(data["phrases"])
                if name == "equivalence"
                else data["keyword"]
            )
            entry = deviations.get((name, subject)) or judgments.get(name, {}).get(subject)
            if entry is None:
                structured = {
                    **_DEFAULTS[name],
                    "confidence": 0.3,
                    "rationale": "Synthetic default: no scripted answer.",
                }
            else:
                structured = {
                    **{k: v for k, v in entry.items() if k not in ("confidence", "rationale")},
                    "confidence": entry.get("confidence", 0.5),
                    "rationale": entry.get("rationale", "scripted"),
                }
                if name == "entity" and structured.get("entity") is None:
                    structured["entity"] = ""
        text = json.dumps(structured, sort_keys=True)
        digest = hashlib.sha256(canonical_json(request).encode("utf-8")).hexdigest()[:16]
        return TransportResponse(
            id=f"synthetic_{digest}",
            model=SYNTHETIC_MODEL,
            stop_reason="end_turn",
            text=text,
            usage={
                "input_tokens": estimate_tokens(request),
                "output_tokens": estimate_tokens(text),
                "cache_read_input_tokens": 0,
                "cache_creation_input_tokens": 0,
            },
            responded_at=SYNTHETIC_TIME,
            transport="scripted",
            synthetic=True,
        )

    return respond
