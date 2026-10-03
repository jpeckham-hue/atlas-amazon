"""Evidence store protocol and the shared in-memory index.

Stores are append-only: there is no update or delete, IDs are unique, and
records come back exactly as written. Query results keep insertion order,
so repeated runs over the same store are deterministic.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import Protocol, runtime_checkable

from atlas_amazon.models import Evidence


class EvidenceStoreError(Exception):
    pass


class DuplicateEvidenceError(EvidenceStoreError):
    def __init__(self, ids: Iterable[str]) -> None:
        self.ids = tuple(ids)
        super().__init__(f"duplicate evidence IDs: {list(self.ids)}")


class EvidenceNotFoundError(EvidenceStoreError, KeyError):
    def __init__(self, evidence_id: str) -> None:
        self.evidence_id = evidence_id
        super().__init__(f"evidence {evidence_id!r} not found")

    def __str__(self) -> str:  # KeyError would repr() the message
        return self.args[0]


class CorruptEvidenceError(EvidenceStoreError):
    def __init__(self, location: str, line: int, reason: str) -> None:
        self.location = location
        self.line = line
        self.reason = reason
        super().__init__(f"{location}:{line}: {reason}")


@runtime_checkable
class EvidenceStore(Protocol):
    def append(self, evidence: Evidence) -> None: ...

    def append_many(self, items: Iterable[Evidence]) -> None:
        """All-or-nothing: if any record is invalid or a duplicate, none are written."""
        ...

    def get(self, evidence_id: str) -> Evidence: ...

    def __contains__(self, evidence_id: object) -> bool: ...

    def __len__(self) -> int: ...

    def __iter__(self) -> Iterator[Evidence]: ...

    def query(
        self,
        *,
        run_id: str | None = None,
        subject: str | None = None,
        kind: str | None = None,
        provider: str | None = None,
        marketplace: str | None = None,
    ) -> list[Evidence]:
        """Records matching every given filter (None = any), in insertion order."""
        ...


class _IndexedEvidence:
    """Insertion-ordered ID index shared by the concrete stores."""

    def __init__(self) -> None:
        self._records: dict[str, Evidence] = {}

    def _check_new(self, items: list[Evidence]) -> None:
        for item in items:
            if not isinstance(item, Evidence):
                raise TypeError(f"expected Evidence, got {type(item).__name__}")
        seen: set[str] = set()
        dupes: list[str] = []
        for item in items:
            if item.id in self._records or item.id in seen:
                dupes.append(item.id)
            seen.add(item.id)
        if dupes:
            raise DuplicateEvidenceError(dupes)

    def _index(self, items: list[Evidence]) -> None:
        for item in items:
            self._records[item.id] = item

    def get(self, evidence_id: str) -> Evidence:
        try:
            return self._records[evidence_id]
        except KeyError:
            raise EvidenceNotFoundError(evidence_id) from None

    def __contains__(self, evidence_id: object) -> bool:
        return evidence_id in self._records

    def __len__(self) -> int:
        return len(self._records)

    def __iter__(self) -> Iterator[Evidence]:
        return iter(list(self._records.values()))

    def query(
        self,
        *,
        run_id: str | None = None,
        subject: str | None = None,
        kind: str | None = None,
        provider: str | None = None,
        marketplace: str | None = None,
    ) -> list[Evidence]:
        wanted = {
            "run_id": run_id,
            "subject": subject,
            "kind": kind,
            "provider": provider,
            "marketplace": marketplace,
        }
        filters = {name: value for name, value in wanted.items() if value is not None}
        return [
            ev
            for ev in self._records.values()
            if all(getattr(ev, name) == value for name, value in filters.items())
        ]


class InMemoryEvidenceStore(_IndexedEvidence):
    """Volatile store with the same contract as the JSONL store. Useful in tests."""

    def append(self, evidence: Evidence) -> None:
        self.append_many([evidence])

    def append_many(self, items: Iterable[Evidence]) -> None:
        batch = list(items)
        self._check_new(batch)
        self._index(batch)
