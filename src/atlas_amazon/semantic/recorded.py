"""Read judgments straight out of a batch recording, re-validated, offline.

A recording made with an older prompt or context can no longer be replayed
through the current pipeline (its request hashes differ), but its exchanges
are still real evidence. `recorded_judgments` rebuilds every judgment a
recording's batch exchanges contain:

* each item's request is reconstructed from the recorded prompt input
  (hoisted context + item), and its ID must equal `item_id(request)`, so a
  result can't be attached to the wrong input;
* results are parsed by ID with the same parser as live responses, and each
  valid one goes through `judgment_evidence` + `parse_judgment`.

`final_judgments` keeps the last answer per (type, input hash), which is
what the pipeline used: an escalated item's strong answer comes after its
fast one.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from atlas_amazon.judgments.contract import (
    Judgment,
    JudgmentError,
    JudgmentRequest,
    JudgmentType,
    judgment_evidence,
    parse_judgment,
)
from atlas_amazon.semantic.batch import BatchItem, item_id, parse_batch_response
from atlas_amazon.semantic.records import ChecksummedJsonl

_INPUT = re.compile(r"<input>\s*(.*?)\s*</input>", re.S)


class RecordingError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class RecordedJudgment:
    judgment: Judgment
    requested_model: str
    exchange: int  # position of the exchange in the recording


def _items(request: dict) -> list[BatchItem] | None:
    match = _INPUT.search(request["messages"][0]["content"])
    if not match:
        return None
    data = json.loads(match.group(1))
    if not isinstance(data, dict) or "items" not in data:
        return None  # not a judgment batch (e.g. review themes)
    items = []
    for entry in data["items"]:
        kind = JudgmentType(entry["type"])
        if kind is JudgmentType.EQUIVALENCE:
            request_ = JudgmentRequest(kind, {"phrases": list(entry["phrases"])})
        else:
            context = data["contexts"][entry["context"]]
            request_ = JudgmentRequest(kind, {"keyword": entry["keyword"], "context": context})
        if item_id(request_) != entry["id"]:
            raise RecordingError(f"item {entry['id']} does not match its reconstructed input")
        items.append(BatchItem(entry["id"], request_))
    return items


def recorded_judgments(
    path: str | os.PathLike[str],
    *,
    prompt_version: str,
    marketplace: str = "US",
    run_id: str | None = None,
    provider: str = "anthropic",
) -> list[RecordedJudgment]:
    out: list[RecordedJudgment] = []
    for position, record in enumerate(ChecksummedJsonl(path).read()):
        request, response = record["request"], record["response"]
        items = _items(request)
        if not items:
            continue
        parsed = parse_batch_response(items, response.get("text"), response.get("stop_reason"))
        for item in items:
            outcome = parsed.outcomes[item.id]
            if not outcome.ok:
                continue
            data = dict(outcome.structured)
            confidence, rationale = data.pop("confidence"), data.pop("rationale")
            if item.request.type is JudgmentType.ENTITY:
                data["entity"] = data.get("entity") or None
            try:
                evidence = judgment_evidence(
                    provider=provider,
                    request=item.request,
                    result=data,
                    confidence=confidence,
                    model=response["model"],
                    prompt_version=prompt_version,
                    rationale=rationale,
                    marketplace=marketplace,
                    judged_at=datetime.fromisoformat(response["responded_at"]),
                    run_id=run_id,
                )
                out.append(RecordedJudgment(parse_judgment(evidence), request["model"], position))
            except (JudgmentError, KeyError, TypeError, ValueError):
                continue
    return out


def final_judgments(recorded: Sequence[RecordedJudgment]) -> list[Judgment]:
    last: dict[tuple[str, str], Judgment] = {}
    for r in recorded:
        last[(r.judgment.type.value, r.judgment.input_hash)] = r.judgment
    return list(last.values())
