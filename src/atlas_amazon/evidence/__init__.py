"""Evidence identity, serialization and append-only storage."""

from atlas_amazon.evidence.identity import evidence_id_for, make_evidence
from atlas_amazon.evidence.jsonl import JsonlEvidenceStore
from atlas_amazon.evidence.serialize import (
    FORMAT_VERSION,
    decode_record,
    encode_record,
    evidence_from_dict,
    evidence_to_dict,
)
from atlas_amazon.evidence.store import (
    CorruptEvidenceError,
    DuplicateEvidenceError,
    EvidenceNotFoundError,
    EvidenceStore,
    EvidenceStoreError,
    InMemoryEvidenceStore,
)

__all__ = [
    "FORMAT_VERSION",
    "CorruptEvidenceError",
    "DuplicateEvidenceError",
    "EvidenceNotFoundError",
    "EvidenceStore",
    "EvidenceStoreError",
    "InMemoryEvidenceStore",
    "JsonlEvidenceStore",
    "decode_record",
    "encode_record",
    "evidence_from_dict",
    "evidence_id_for",
    "evidence_to_dict",
    "make_evidence",
]
