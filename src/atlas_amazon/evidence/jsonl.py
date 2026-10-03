"""Append-only JSONL evidence store.

* The file is opened only in append mode. Nothing ever rewrites or
  truncates it.
* Every line carries a SHA-256 of its evidence, and the whole file is
  validated on open. Malformed JSON, a checksum mismatch, a truncated last
  line, a blank line or a duplicate ID raises CorruptEvidenceError with the
  line number. Nothing is silently skipped.
* A batch is validated in full before any byte is written, then written in
  one call and fsynced.
* `verify()` re-reads the file and confirms it still matches what this
  store wrote, which catches edits made by other processes.

Single-writer only: there is no cross-process locking.
"""

from __future__ import annotations

import os
from collections.abc import Iterable
from pathlib import Path

from atlas_amazon.evidence.serialize import decode_record, encode_record
from atlas_amazon.evidence.store import CorruptEvidenceError, _IndexedEvidence
from atlas_amazon.models import Evidence


def _read_records(path: Path) -> list[Evidence]:
    records: list[Evidence] = []
    seen: set[str] = set()
    with path.open("r", encoding="utf-8", newline="") as handle:
        for lineno, line in enumerate(handle, 1):
            if not line.endswith("\n"):
                raise CorruptEvidenceError(str(path), lineno, "truncated record (no newline)")
            if not line.strip():
                raise CorruptEvidenceError(str(path), lineno, "blank line")
            try:
                evidence = decode_record(line)
            except ValueError as exc:
                raise CorruptEvidenceError(str(path), lineno, str(exc)) from exc
            if evidence.id in seen:
                raise CorruptEvidenceError(
                    str(path), lineno, f"duplicate evidence ID {evidence.id!r}"
                )
            seen.add(evidence.id)
            records.append(evidence)
    return records


class JsonlEvidenceStore(_IndexedEvidence):
    def __init__(self, path: str | os.PathLike[str]) -> None:
        super().__init__()
        self.path = Path(path)
        if self.path.exists():
            self._index(_read_records(self.path))

    def append(self, evidence: Evidence) -> None:
        self.append_many([evidence])

    def append_many(self, items: Iterable[Evidence]) -> None:
        batch = list(items)
        self._check_new(batch)
        if not batch:
            return
        payload = "".join(encode_record(item) for item in batch)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        self._index(batch)

    def verify(self) -> None:
        """Re-read the file and confirm it matches this store's records exactly."""
        on_disk = _read_records(self.path) if self.path.exists() else []
        expected = list(self._records.values())
        for lineno, (disk, mine) in enumerate(zip(on_disk, expected, strict=False), 1):
            if disk != mine:
                raise CorruptEvidenceError(str(self.path), lineno, "record differs from store")
        if len(on_disk) != len(expected):
            raise CorruptEvidenceError(
                str(self.path),
                min(len(on_disk), len(expected)) + 1,
                f"file has {len(on_disk)} records, store has {len(expected)}",
            )
