"""Persistent semantic cache.

An entry is reusable only when **all** of these match:

* `kind`: the judgment type (or "review_themes");
* `input_hash`: of the exact input judged;
* `provider` and `model`: as configured for the request;
* `prompt_version`;
* `prompt_fingerprint`: the hash of the template text and schema. This
  guards against a template edited without a version bump. A mismatch
  counts as a *stale* miss.

Entries store the model's structured output and the call metadata, never a
finished verdict. A hit is rebuilt into Evidence through exactly the same
validation as a live response, so cached output can't bypass validation
either. The file is append-only and checksummed (`records.ChecksummedJsonl`),
and it holds no credentials (checked on write).
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from typing import Any

from atlas_amazon.semantic.records import ChecksummedJsonl


@dataclass(frozen=True, slots=True)
class CacheKey:
    kind: str
    input_hash: str
    provider: str
    model: str
    prompt_version: str


@dataclass(frozen=True, slots=True)
class CacheLookup:
    entry: dict[str, Any] | None
    reason: str  # "hit" | "absent" | "stale_prompt"


class SemanticCache:
    def __init__(self, path: str | os.PathLike[str]) -> None:
        self._file = ChecksummedJsonl(path)
        self._entries: dict[CacheKey, list[dict[str, Any]]] = {}
        for record in self._file.read():
            key = CacheKey(**record["key"])
            self._entries.setdefault(key, []).append(record)

    @property
    def path(self):
        return self._file.path

    def lookup(self, key: CacheKey, prompt_fingerprint: str) -> CacheLookup:
        candidates = self._entries.get(key, [])
        for record in reversed(candidates):  # newest first
            if record["prompt_fingerprint"] == prompt_fingerprint:
                return CacheLookup(record["value"], "hit")
        return CacheLookup(None, "stale_prompt" if candidates else "absent")

    def put(self, key: CacheKey, prompt_fingerprint: str, value: dict[str, Any]) -> None:
        record = {"key": asdict(key), "prompt_fingerprint": prompt_fingerprint, "value": value}
        self._file.append([record])
        self._entries.setdefault(key, []).append(record)

    def __len__(self) -> int:
        return sum(len(v) for v in self._entries.values())
