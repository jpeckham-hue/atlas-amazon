"""Human review of stale or disputed reference judgments (v0.8).

Fixture judgments were written before judgments could see the seller's full
first-party context, so some may now be wrong. Atlas never rewrites them.
Instead a reviewer records decisions in a review file:

    {
      "reviewer": "jeff",                       # required once any decision is set
      "decided_at": "2026-10-05T09:00:00+00:00", # ISO 8601 with offset
      "decisions": [
        {"scenario": "book_cozy_mystery", "type": "relevance", "subject": "harbor town",
         "decision": {"score": 0.4},             # null = not decided yet
         "rationale": "Setting is evidenced, but weak as a search."}
      ]
    }

`load_review_decisions` turns decided entries into a `HumanJudgmentProvider`
per scenario. Its answers are ordinary `human` judgment Evidence (same
validation, `prompt_version = "human-review-v1"`), so they can run as the
`human_judgments` provider and they become the evaluation reference via
`supersede`, which replaces reference judgments of the same (type, subject)
while every fixture and model judgment stays in the record.
"""

from __future__ import annotations

import json
import os
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from atlas_amazon.judgments.contract import Judgment, JudgmentError, JudgmentRequest, parse_judgment
from atlas_amazon.semantic.human import HumanJudgmentProvider


def load_review_decisions(path: str | os.PathLike[str]) -> dict[str, HumanJudgmentProvider]:
    """Scenario name -> provider of the decided entries (scenarios with none are omitted)."""
    data: dict[str, Any] = json.loads(Path(path).read_text(encoding="utf-8"))
    decided = [d for d in data.get("decisions", ()) if d.get("decision") is not None]
    if not decided:
        return {}
    markets: dict[str, dict[str, dict[str, dict[str, Any]]]] = {}
    for entry in decided:
        if not str(entry.get("rationale") or "").strip():
            raise JudgmentError(f"decision for {entry.get('subject')!r} needs a rationale")
        block = markets.setdefault(entry["scenario"], {})
        block.setdefault(entry["type"], {})[entry["subject"]] = {
            **entry["decision"],
            "confidence": 1.0,
            "rationale": entry["rationale"],
        }
    return {
        scenario: HumanJudgmentProvider(
            {
                "reviewer": data.get("reviewer"),
                "decided_at": data.get("decided_at"),
                "markets": {entry_market(data): types},
            }
        )
        for scenario, types in markets.items()
    }


def entry_market(data: dict[str, Any]) -> str:
    return str(data.get("marketplace", "US"))


def human_judgments(
    provider: HumanJudgmentProvider,
    requests: Sequence[JudgmentRequest],
    *,
    marketplace: str = "US",
    run_id: str | None = None,
) -> list[Judgment]:
    return [
        parse_judgment(e) for e in provider.judge(requests, marketplace=marketplace, run_id=run_id)
    ]


def supersede(reference: Sequence[Judgment], overrides: Sequence[Judgment]) -> list[Judgment]:
    """`reference` with each (type, subject) that `overrides` answers replaced.

    Neither input is modified; overrides for subjects the reference lacks are
    added. Typical use: fixture judgments superseded by human review decisions.
    """
    replaced = {(j.type.value, j.subject): j for j in overrides}
    out = [replaced.pop((j.type.value, j.subject), j) for j in reference]
    return out + list(replaced.values())
