"""Batched judgment requests: item IDs, prompt input, and per-item response parsing.

Pure functions; no transport, cache or evidence here (see `batched.py`).

**Item IDs** are derived from the request, never from its position:
`<type prefix>-<first 10 hex of the input hash>` (e.g. `rel-3fa9c2d81e`).
The type prefix lets the parser reject an answer of the wrong type, and the
hash part makes the ID stable across batches, runs and replays. Items are
sorted by subject, then ID, so the same set of requests always renders the
same request (and the same request hash for replay), whatever order they
arrived in, and a keyword's relevance, intent and entity items sit together
in one batch.

**Prompt input** hoists the product context shared by many items:

    {"contexts": {"C1": {"product_title": ..., "seeds": [...]}},
     "items": [{"id": "rel-...", "type": "relevance", "keyword": "...", "context": "C1"},
               {"id": "eqv-...", "type": "equivalence", "phrases": ["a", "b"]}]}

The input hash of each request still covers its full, un-hoisted input.

**Parsing** maps results to requests by ID only. Order is irrelevant (and
reported when it differs). Per item, the outcome is one of:

* `ok`: exactly one result with this ID, of the right type and shape;
* `missing`: no result carries this ID;
* `duplicate`: two or more results carry this ID. All copies are rejected,
  since there is no principled way to choose one;
* `type_mismatch`: the result's type differs from the request's;
* `malformed`: the result has missing or extra fields;
* `refusal` / `batch_malformed`: the whole response was a refusal, or was
  not a JSON object with a `results` array (for example, truncated output).

Results with an ID no request has are reported as `unknown_ids` and ignored.
One bad item never invalidates its siblings.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from atlas_amazon.jsonvalue import canonical_json, thaw
from atlas_amazon.judgments.contract import JudgmentRequest, JudgmentType

ID_PREFIX = {
    JudgmentType.RELEVANCE: "rel",
    JudgmentType.INTENT: "int",
    JudgmentType.ENTITY: "ent",
    JudgmentType.EQUIVALENCE: "eqv",
}
ID_HEX = 10
RESULT_FIELDS = {
    JudgmentType.RELEVANCE: frozenset({"score"}),
    JudgmentType.INTENT: frozenset({"label", "score"}),
    JudgmentType.ENTITY: frozenset({"label", "entity"}),
    JudgmentType.EQUIVALENCE: frozenset({"equivalent"}),
}
AUDIT_FIELDS = frozenset({"confidence", "rationale"})

OK = "ok"
MISSING = "missing"
DUPLICATE = "duplicate"
TYPE_MISMATCH = "type_mismatch"
MALFORMED = "malformed"
REFUSAL = "refusal"
BATCH_MALFORMED = "batch_malformed"


class BatchError(ValueError):
    pass


def item_id(request: JudgmentRequest) -> str:
    digest = request.input_hash.removeprefix("sha256:")
    return f"{ID_PREFIX[request.type]}-{digest[:ID_HEX]}"


@dataclass(frozen=True, slots=True)
class BatchItem:
    id: str
    request: JudgmentRequest


def batch_items(requests: Sequence[JudgmentRequest]) -> tuple[BatchItem, ...]:
    """One item per distinct request, sorted by (subject, ID). ID collisions are refused."""
    by_id: dict[str, BatchItem] = {}
    for request in requests:
        iid = item_id(request)
        existing = by_id.get(iid)
        if existing is not None:
            if existing.request.input_hash != request.input_hash:
                raise BatchError(f"item id collision on {iid}")  # astronomically unlikely
            continue
        by_id[iid] = BatchItem(iid, request)
    return tuple(sorted(by_id.values(), key=lambda i: (i.request.subject, i.id)))


def render_batch_input(items: Sequence[BatchItem]) -> dict[str, Any]:
    contexts: dict[str, str] = {}  # canonical context JSON -> label
    context_values: dict[str, Any] = {}
    rendered = []
    for item in items:
        request = item.request
        entry: dict[str, Any] = {"id": item.id, "type": request.type.value}
        if request.type is JudgmentType.EQUIVALENCE:
            entry["phrases"] = list(request.input["phrases"])
        else:
            context = thaw(request.input["context"])
            key = canonical_json(context)
            if key not in contexts:
                contexts[key] = f"C{len(contexts) + 1}"
                context_values[contexts[key]] = context
            entry["keyword"] = request.input["keyword"]
            entry["context"] = contexts[key]
        rendered.append(entry)
    return {"contexts": context_values, "items": rendered}


@dataclass(frozen=True, slots=True)
class ItemOutcome:
    id: str
    request: JudgmentRequest
    status: str
    structured: Mapping[str, Any] | None = None  # result + confidence + rationale, when ok
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.status == OK


@dataclass(frozen=True, slots=True)
class BatchParse:
    outcomes: Mapping[str, ItemOutcome]  # by item id, one per requested item
    unknown_ids: tuple[str, ...] = ()
    unattributable: int = 0  # results without a usable string id
    out_of_order: bool = False
    batch_error: str | None = None  # set when the response as a whole is unusable
    notes: tuple[str, ...] = field(default_factory=tuple)

    def count(self, status: str) -> int:
        return sum(1 for o in self.outcomes.values() if o.status == status)


def _all(items: Sequence[BatchItem], status: str, detail: str) -> dict[str, ItemOutcome]:
    return {i.id: ItemOutcome(i.id, i.request, status, detail=detail) for i in items}


def parse_batch_response(
    items: Sequence[BatchItem], text: str | None, stop_reason: str | None
) -> BatchParse:
    if stop_reason == "refusal":
        return BatchParse(_all(items, REFUSAL, "model declined the batch"), batch_error=REFUSAL)
    try:
        if not text:
            raise BatchError("no text block")
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise BatchError(f"not JSON ({stop_reason})") from exc
        if not isinstance(data, dict) or set(data) != {"results"}:
            raise BatchError("expected an object with only 'results'")
        if not isinstance(data["results"], list):
            raise BatchError("'results' is not an array")
    except BatchError as exc:
        return BatchParse(_all(items, BATCH_MALFORMED, str(exc)), batch_error=BATCH_MALFORMED)

    wanted = {i.id: i for i in items}
    grouped: dict[str, list[dict[str, Any]]] = {}
    order: list[str] = []
    unknown: list[str] = []
    unattributable = 0
    for entry in data["results"]:
        if not isinstance(entry, dict) or not isinstance(entry.get("id"), str):
            unattributable += 1
            continue
        rid = entry["id"]
        if rid not in wanted:
            unknown.append(rid)
            continue
        if rid not in grouped:
            order.append(rid)
        grouped.setdefault(rid, []).append(entry)

    outcomes: dict[str, ItemOutcome] = {}
    for item in items:
        request = item.request
        entries = grouped.get(item.id)
        if not entries:
            outcomes[item.id] = ItemOutcome(item.id, request, MISSING, detail="no result")
            continue
        if len(entries) > 1:
            outcomes[item.id] = ItemOutcome(
                item.id, request, DUPLICATE, detail=f"{len(entries)} results with this id"
            )
            continue
        entry = entries[0]
        if entry.get("type") != request.type.value:
            outcomes[item.id] = ItemOutcome(
                item.id,
                request,
                TYPE_MISMATCH,
                detail=f"answered as {entry.get('type')!r}, asked {request.type.value!r}",
            )
            continue
        expected = RESULT_FIELDS[request.type] | AUDIT_FIELDS | {"id", "type"}
        if set(entry) != expected:
            outcomes[item.id] = ItemOutcome(
                item.id,
                request,
                MALFORMED,
                detail=f"fields {sorted(entry)} != {sorted(expected)}",
            )
            continue
        structured = {k: v for k, v in entry.items() if k not in ("id", "type")}
        outcomes[item.id] = ItemOutcome(item.id, request, OK, structured)
    asked = [i.id for i in items if i.id in grouped]
    notes = []
    if unknown:
        notes.append(f"ignored results for unknown ids {sorted(set(unknown))}")
    if unattributable:
        notes.append(f"ignored {unattributable} results without a string id")
    return BatchParse(
        outcomes,
        unknown_ids=tuple(unknown),
        unattributable=unattributable,
        out_of_order=order != asked,
        notes=tuple(notes),
    )


def chunk(items: Sequence[BatchItem], max_items: int) -> list[tuple[BatchItem, ...]]:
    """Split into the fewest batches of at most max_items, balanced in size."""
    if max_items < 1:
        raise ValueError("max_items must be >= 1")
    if not items:
        return []
    count = -(-len(items) // max_items)
    size, extra = divmod(len(items), count)
    out, start = [], 0
    for i in range(count):
        end = start + size + (1 if i < extra else 0)
        out.append(tuple(items[start:end]))
        start = end
    return out
