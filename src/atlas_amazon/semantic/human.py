"""Human judgments: reviewer decisions recorded with the same evidence model.

A human judgment is ordinary `judgment` Evidence with
`provider = "human"`, `model = "human:<reviewer>"` and
`prompt_version = "human-review-v1"`, built by `judgment_evidence`, so it
passes the same validation. It overrides a model judgment for the same
(type, input hash). Both records are kept, and the run reports which one
supplied the signal (see `resolve_judgments`).

`HumanJudgmentProvider` answers from a block of reviewer decisions:

    {"reviewer": "jeff", "decided_at": "2026-10-03T12:00:00+00:00",
     "markets": {"US": {"relevance": {"cozy mystery series": {
         "score": 0.9, "confidence": 1.0, "rationale": "Book 1 of a series."}}}}}

Keys are normalized keywords, or "a || b" for equivalence, as in fixtures.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from atlas_amazon.judgments.contract import (
    HUMAN_PROMPT_VERSION,
    HUMAN_PROVIDER,
    Judgment,
    JudgmentError,
    JudgmentRequest,
    JudgmentType,
    judgment_evidence,
)
from atlas_amazon.models import Evidence


class HumanJudgmentProvider:
    name = HUMAN_PROVIDER

    def __init__(self, block: Mapping[str, Any]) -> None:
        reviewer = block.get("reviewer")
        if not isinstance(reviewer, str) or not reviewer.strip():
            raise JudgmentError("human judgments need a reviewer")
        try:
            self.decided_at = datetime.fromisoformat(block["decided_at"])
        except (KeyError, TypeError, ValueError):
            raise JudgmentError("human judgments need an ISO 8601 decided_at") from None
        if self.decided_at.utcoffset() is None:
            raise JudgmentError("decided_at must include a UTC offset")
        self.reviewer = reviewer
        self.markets = block.get("markets", {})

    def judge(
        self, requests: Sequence[JudgmentRequest], *, marketplace: str, run_id: str | None = None
    ) -> list[Evidence]:
        market = self.markets.get(marketplace, {})
        out, seen = [], set()
        for request in requests:
            if request.input_hash in seen:
                continue
            seen.add(request.input_hash)
            entry = market.get(request.type.value, {}).get(request.subject)
            if entry is None:
                continue
            outcome = {k: v for k, v in entry.items() if k not in ("confidence", "rationale")}
            out.append(
                judgment_evidence(
                    provider=HUMAN_PROVIDER,
                    request=request,
                    result=outcome,
                    confidence=entry.get("confidence"),
                    model=f"human:{self.reviewer}",
                    prompt_version=HUMAN_PROMPT_VERSION,
                    rationale=entry.get("rationale", ""),
                    marketplace=marketplace,
                    judged_at=self.decided_at,
                    run_id=run_id,
                )
            )
        return out


@dataclass(frozen=True, slots=True)
class JudgmentResolution:
    type: JudgmentType
    subject: str
    input_hash: str
    model: Judgment | None
    human: Judgment | None

    @property
    def used(self) -> Judgment:
        return self.human or self.model  # type: ignore[return-value]

    @property
    def overridden(self) -> bool:
        return self.human is not None and self.model is not None


def resolve_judgments(judgments: Sequence[Judgment]) -> tuple[JudgmentResolution, ...]:
    """Pair model and human judgments per (type, input hash). The human judgment wins."""
    order: list[tuple[str, str]] = []
    model: dict[tuple[str, str], Judgment] = {}
    human: dict[tuple[str, str], Judgment] = {}
    for j in judgments:
        key = (j.type.value, j.input_hash)
        if key not in model and key not in human:
            order.append(key)
        target = human if j.is_human else model
        target.setdefault(key, j)
    return tuple(
        JudgmentResolution(
            type=JudgmentType(kind),
            subject=(human.get((kind, h)) or model[(kind, h)]).subject,
            input_hash=h,
            model=model.get((kind, h)),
            human=human.get((kind, h)),
        )
        for kind, h in order
    )
