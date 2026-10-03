"""Content-addressed evidence IDs.

The ID hashes everything that defines an observation except the time it
was retrieved: provider, kind, marketplace, subject, run and payload. The
same observation made twice within one run gets the same ID, so the store
rejects it as a duplicate instead of double-counting it. A new run, or a
changed payload, gets a new ID.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from atlas_amazon.jsonvalue import canonical_json
from atlas_amazon.models import Evidence

ID_PREFIX = "ev_"
_DIGEST_CHARS = 24  # 96 bits; collisions are not a practical concern at this scale


def evidence_id_for(
    *,
    provider: str,
    kind: str,
    marketplace: str,
    subject: str | None,
    run_id: str | None,
    payload: Mapping[str, Any],
) -> str:
    identity = {
        "provider": provider,
        "kind": kind,
        "marketplace": marketplace,
        "subject": subject,
        "run_id": run_id,
        "payload": payload,
    }
    digest = hashlib.sha256(canonical_json(identity).encode("utf-8")).hexdigest()
    return ID_PREFIX + digest[:_DIGEST_CHARS]


def make_evidence(
    *,
    provider: str,
    kind: str,
    marketplace: str,
    retrieved_at: datetime,
    payload: Mapping[str, Any],
    subject: str | None = None,
    run_id: str | None = None,
    source_url: str | None = None,
) -> Evidence:
    """Build an Evidence record with its content-addressed ID."""
    kind = str(kind)  # store enum members as their plain value
    return Evidence(
        id=evidence_id_for(
            provider=provider,
            kind=kind,
            marketplace=marketplace,
            subject=subject,
            run_id=run_id,
            payload=payload,
        ),
        kind=kind,
        provider=provider,
        marketplace=marketplace,
        retrieved_at=retrieved_at,
        payload=payload,
        source_url=source_url,
        subject=subject,
        run_id=run_id,
    )
