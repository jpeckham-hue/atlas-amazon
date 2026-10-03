"""Evidence <-> JSON records.

One JSONL line per record:

    {"evidence": {...}, "sha256": "<hex of canonical evidence JSON>", "v": 1}

The checksum covers the canonical JSON of the `evidence` object, so any
edit to a stored record (a payload value, a timestamp, the ID) is detected
on load.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from atlas_amazon.jsonvalue import canonical_json, thaw
from atlas_amazon.models import Evidence

FORMAT_VERSION = 1
_EVIDENCE_KEYS = frozenset(
    {
        "id",
        "kind",
        "provider",
        "marketplace",
        "retrieved_at",
        "payload",
        "source_url",
        "subject",
        "run_id",
    }
)
_RECORD_KEYS = frozenset({"v", "sha256", "evidence"})


def evidence_to_dict(evidence: Evidence) -> dict[str, Any]:
    return {
        "id": evidence.id,
        "kind": evidence.kind,
        "provider": evidence.provider,
        "marketplace": evidence.marketplace,
        "retrieved_at": evidence.retrieved_at.isoformat(),
        "payload": thaw(evidence.payload),
        "source_url": evidence.source_url,
        "subject": evidence.subject,
        "run_id": evidence.run_id,
    }


def evidence_from_dict(data: Any) -> Evidence:
    if not isinstance(data, dict):
        raise ValueError("evidence must be a JSON object")
    if set(data) != _EVIDENCE_KEYS:
        missing = sorted(_EVIDENCE_KEYS - set(data))
        extra = sorted(set(data) - _EVIDENCE_KEYS)
        raise ValueError(f"evidence keys mismatch (missing {missing}, unexpected {extra})")
    try:
        retrieved_at = datetime.fromisoformat(data["retrieved_at"])
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid retrieved_at: {data['retrieved_at']!r}") from exc
    try:
        return Evidence(
            id=data["id"],
            kind=data["kind"],
            provider=data["provider"],
            marketplace=data["marketplace"],
            retrieved_at=retrieved_at,
            payload=data["payload"],
            source_url=data["source_url"],
            subject=data["subject"],
            run_id=data["run_id"],
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid evidence: {exc}") from exc


def _checksum(evidence_dict: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(evidence_dict).encode("utf-8")).hexdigest()


def encode_record(evidence: Evidence) -> str:
    """One newline-terminated JSONL line."""
    body = evidence_to_dict(evidence)
    record = {"v": FORMAT_VERSION, "sha256": _checksum(body), "evidence": body}
    return canonical_json(record) + "\n"


def decode_record(line: str) -> Evidence:
    """Parse and verify one JSONL line. Raises ValueError describing the problem."""
    try:
        record = json.loads(line)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON: {exc.msg}") from exc
    if not isinstance(record, dict) or set(record) != _RECORD_KEYS:
        raise ValueError("record must be an object with exactly 'v', 'sha256', 'evidence'")
    if record["v"] != FORMAT_VERSION:
        raise ValueError(f"unsupported record version {record['v']!r}")
    if not isinstance(record["evidence"], dict):
        raise ValueError("evidence must be a JSON object")
    if record["sha256"] != _checksum(record["evidence"]):
        raise ValueError("checksum mismatch (record was modified or damaged)")
    return evidence_from_dict(record["evidence"])
