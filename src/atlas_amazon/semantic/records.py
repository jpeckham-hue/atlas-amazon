"""Append-only, checksummed JSONL files for the semantic layer, plus a secret guard.

Used by the semantic cache and the response recordings. One line per record:

    {"record": {...}, "sha256": "<hex of canonical record JSON>", "v": 1}

Like the evidence store, files are only ever appended to, and damage is
detected on open (bad JSON, checksum mismatch, a truncated last line).

`ensure_no_secrets` runs before anything is written to disk or put into
Evidence: credentials must never land in recordings, caches, evidence or
reports.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from atlas_amazon.jsonvalue import canonical_json, thaw

FORMAT_VERSION = 1

# Patterns that look like credentials. Deliberately broad: a false positive
# blocks a write, which is safer than leaking a key.
_SECRET_PATTERNS = (
    re.compile(r"sk-ant-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-]{20,}"),
    re.compile(
        r"(?i)\b(x-api-key|api[_-]?key|authorization)\b\s*[\"':=]+\s*[\"']?[A-Za-z0-9._\-]{16,}"
    ),
    # Login with Amazon (SP-API): access tokens, refresh tokens, client secrets.
    re.compile(r"\bAtz[ar]\|[A-Za-z0-9_\-]{8,}"),
    re.compile(r"\bamzn1\.oa2-cs\.v1\.[A-Za-z0-9]{16,}"),
)
_SECRET_FIELD_NAMES = frozenset(
    {
        "api_key",
        "x-api-key",
        "authorization",
        "auth_token",
        "x-amz-access-token",
        "access_token",
        "refresh_token",
        "client_secret",
    }
)


class RecordFileError(Exception):
    def __init__(self, path: Path, line: int, reason: str) -> None:
        self.path, self.line, self.reason = path, line, reason
        super().__init__(f"{path}:{line}: {reason}")


class SecretLeakError(ValueError):
    pass


def find_secrets(value: Any, path: str = "$") -> list[str]:
    """Paths inside `value` that look like credentials (field names or token patterns)."""
    found: list[str] = []
    value = thaw(value)
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(key, str) and key.lower() in _SECRET_FIELD_NAMES and item:
                found.append(f"{path}.{key}")
            found.extend(find_secrets(item, f"{path}.{key}"))
    elif isinstance(value, list):
        for i, item in enumerate(value):
            found.extend(find_secrets(item, f"{path}[{i}]"))
    elif isinstance(value, str) and any(p.search(value) for p in _SECRET_PATTERNS):
        found.append(path)
    return found


def ensure_no_secrets(value: Any, where: str) -> None:
    leaks = find_secrets(value)
    if leaks:
        raise SecretLeakError(f"refusing to write {where}: possible credentials at {leaks}")


def _checksum(record: Any) -> str:
    return hashlib.sha256(canonical_json(record).encode("utf-8")).hexdigest()


class ChecksummedJsonl:
    """An append-only list of JSON records on disk."""

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self.path = Path(path)

    def read(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8", newline="") as handle:
            for lineno, line in enumerate(handle, 1):
                if not line.endswith("\n"):
                    raise RecordFileError(self.path, lineno, "truncated record (no newline)")
                try:
                    wrapper = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise RecordFileError(self.path, lineno, f"invalid JSON: {exc.msg}") from exc
                if not isinstance(wrapper, dict) or set(wrapper) != {"v", "sha256", "record"}:
                    raise RecordFileError(self.path, lineno, "malformed record wrapper")
                if wrapper["v"] != FORMAT_VERSION:
                    raise RecordFileError(self.path, lineno, f"unsupported version {wrapper['v']}")
                if wrapper["sha256"] != _checksum(wrapper["record"]):
                    raise RecordFileError(self.path, lineno, "checksum mismatch")
                records.append(wrapper["record"])
        return records

    def append(self, records: Iterable[dict[str, Any]]) -> None:
        lines = []
        for record in records:
            ensure_no_secrets(record, str(self.path))
            body = thaw(record)
            lines.append(
                canonical_json({"v": FORMAT_VERSION, "sha256": _checksum(body), "record": body})
                + "\n"
            )
        if not lines:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write("".join(lines))
            handle.flush()
            os.fsync(handle.fileno())
