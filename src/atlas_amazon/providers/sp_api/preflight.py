"""Offline check of the local prerequisites for live SP-API calls. Never prints values.

`market_prerequisites()` looks only at the environment (and optionally the
recordings directory). It makes no network call, so it can run anywhere,
including CI. Each result names the prerequisite and says whether it is
present; for credentials it may add a format hint ("does not look like an LWA
client ID") but never echoes the value or any part of it.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from atlas_amazon.providers.sp_api.http import CREDENTIAL_ENV, LIVE_MARKET_FLAG

# Documented LWA formats; a mismatch is a warning, not a failure.
FORMAT_HINTS: Mapping[str, tuple[str, str]] = {
    "SP_API_LWA_CLIENT_ID": ("amzn1.application-oa2-client.", "an LWA client ID"),
    "SP_API_REFRESH_TOKEN": ("Atzr|", "an LWA refresh token"),
}


@dataclass(frozen=True, slots=True)
class Prerequisite:
    name: str
    ok: bool
    detail: str  # never contains a credential value


def market_prerequisites(
    env: Mapping[str, str] | None = None, recordings_dir: Path | None = None
) -> list[Prerequisite]:
    env = os.environ if env is None else env
    out = []
    for name in CREDENTIAL_ENV:
        value = (env.get(name) or "").strip()
        if not value:
            out.append(Prerequisite(name, False, "missing"))
            continue
        hint = FORMAT_HINTS.get(name)
        if hint and not value.startswith(hint[0]):
            out.append(Prerequisite(name, True, f"set, but does not look like {hint[1]}"))
        else:
            out.append(Prerequisite(name, True, "set"))
    flag = env.get(LIVE_MARKET_FLAG)
    out.append(
        Prerequisite(
            LIVE_MARKET_FLAG,
            flag == "1",
            "set to 1" if flag == "1" else ("missing" if flag is None else "set, but not to 1"),
        )
    )
    if recordings_dir is not None:
        fresh = not recordings_dir.exists() or not any(recordings_dir.iterdir())
        out.append(
            Prerequisite(
                f"recordings directory {recordings_dir.name}/",
                fresh,
                "fresh" if fresh else "already has recordings (will not overwrite)",
            )
        )
    return out


def missing_prerequisites(prerequisites: list[Prerequisite]) -> list[str]:
    return [p.name for p in prerequisites if not p.ok]


def render_prerequisites(prerequisites: list[Prerequisite]) -> str:
    return "\n".join(f"  [{'ok' if p.ok else '--'}] {p.name}: {p.detail}" for p in prerequisites)
