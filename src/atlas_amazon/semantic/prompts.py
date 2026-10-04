"""Versioned prompt templates for semantic providers.

Templates live in `semantic/prompts/<name>.toml` with fields:

    name           = "relevance"          # judgment type, or "review_themes"
    version        = "relevance-v1"       # recorded on every judgment and cache key
    max_tokens     = 256                # cap; batch requests compute their own
    system         = (multi-line TOML string)
    user           = (multi-line TOML string containing {input_json}, the only placeholder)

The JSON output schema for each name is defined here in code, derived from
the judgment contract, and is part of the template fingerprint.

**Version discipline**: `prompts/lock.json` pins the sha256 of every
version (system + user + schema + max_tokens), current and historical.

**Historical versions** stay loadable for replay: when a template is bumped,
its previous file is kept verbatim as `prompts/history/<version>.toml`, and
`load_template(name, version)` returns it. Recordings made with an older
prompt therefore still replay exactly (their request hashes include the
prompt text). Changing a template or its
schema without bumping `version` fails `tests/test_semantic_prompts.py`,
so a recorded or cached result can never silently refer to different
wording. Cache entries also store the fingerprint and are treated as stale
if it differs.
"""

from __future__ import annotations

import hashlib
import json
import tomllib
from dataclasses import dataclass
from importlib import resources
from typing import Any

from atlas_amazon.jsonvalue import canonical_json
from atlas_amazon.judgments.contract import ENTITY_LABELS, INTENT_LABELS, JudgmentType
from atlas_amazon.reviews.themes import Polarity

REVIEW_THEMES = "review_themes"
JUDGMENT_BATCH = "judgment_batch"
PLACEHOLDER = "{input_json}"


def _obj(properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


_AUDIT = {
    "confidence": {"type": "number", "description": "0 to 1"},
    "rationale": {"type": "string", "description": "At most 25 words an auditor can check."},
}

# Result fields per judgment type (without the audit fields).
_RESULT_FIELDS: dict[str, dict[str, Any]] = {
    JudgmentType.RELEVANCE.value: {"score": {"type": "number"}},
    JudgmentType.INTENT.value: {
        "label": {"type": "string", "enum": list(INTENT_LABELS)},
        "score": {"type": "number"},
    },
    JudgmentType.ENTITY.value: {
        "label": {"type": "string", "enum": list(ENTITY_LABELS)},
        "entity": {"type": "string", "description": "The entity named, or empty string"},
    },
    JudgmentType.EQUIVALENCE.value: {"equivalent": {"type": "boolean"}},
}


def _batch_item(kind: str) -> dict[str, Any]:
    return _obj(
        {
            "id": {"type": "string"},
            "type": {"type": "string", "enum": [kind]},
            **_RESULT_FIELDS[kind],
            **_AUDIT,
        }
    )


# Structured-output schemas. Numeric ranges and enums are re-checked by the
# judgment / review-theme validators, which every response must pass.
OUTPUT_SCHEMAS: dict[str, dict[str, Any]] = {
    **{kind: _obj({**fields, **_AUDIT}) for kind, fields in _RESULT_FIELDS.items()},
    # One schema for every batch, whatever types it holds, so the API compiles
    # a single grammar. Items are told apart by "type" and matched by "id".
    JUDGMENT_BATCH: _obj(
        {"results": {"type": "array", "items": {"anyOf": [_batch_item(k) for k in _RESULT_FIELDS]}}}
    ),
    REVIEW_THEMES: _obj(
        {
            "themes": {
                "type": "array",
                "items": _obj(
                    {
                        "theme": {"type": "string"},
                        "polarity": {"type": "string", "enum": [p.value for p in Polarity]},
                        "review_refs": {"type": "array", "items": {"type": "string"}},
                        "terms": {"type": "array", "items": {"type": "string"}},
                        "rationale": {"type": "string"},
                    }
                ),
            },
        }
    ),
}


class PromptError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class PromptTemplate:
    name: str
    version: str
    max_tokens: int
    system: str
    user: str
    schema: dict[str, Any]

    @property
    def fingerprint(self) -> str:
        body = {
            "name": self.name,
            "version": self.version,
            "max_tokens": self.max_tokens,
            "system": self.system,
            "user": self.user,
            "schema": self.schema,
        }
        return hashlib.sha256(canonical_json(body).encode("utf-8")).hexdigest()

    def render_user(self, input_data: Any) -> str:
        return self.user.replace(
            PLACEHOLDER, json.dumps(input_data, indent=2, ensure_ascii=False, sort_keys=True)
        )


def _prompt_dir():
    return resources.files("atlas_amazon.semantic").joinpath("prompts")


def _template_path(name: str, version: str | None):
    current = _prompt_dir().joinpath(f"{name}.toml")
    if version is None:
        return current
    if (
        current.is_file()
        and tomllib.loads(current.read_text(encoding="utf-8")).get("version") == version
    ):
        return current
    return _prompt_dir().joinpath("history").joinpath(f"{version}.toml")


def load_template(name: str, version: str | None = None) -> PromptTemplate:
    """The current template, or a historical `version` kept in prompts/history/."""
    path = _template_path(name, version)
    if not path.is_file():
        raise PromptError(f"no prompt template for {name!r}" + (f" {version}" if version else ""))
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    expected = {"name", "version", "max_tokens", "system", "user"}
    if set(data) != expected:
        raise PromptError(f"{name}.toml must define exactly {sorted(expected)}")
    if data["name"] != name or name not in OUTPUT_SCHEMAS:
        raise PromptError(f"{name}.toml has name {data['name']!r}")
    if version is not None and data["version"] != version:
        raise PromptError(f"{path.name} holds version {data['version']!r}, not {version!r}")
    if not data["version"].startswith(f"{name}-") or data["user"].count(PLACEHOLDER) != 1:
        raise PromptError(
            f"{name}.toml: version must start with '{name}-' and user must "
            f"contain {PLACEHOLDER} exactly once"
        )
    return PromptTemplate(
        name,
        data["version"],
        int(data["max_tokens"]),
        data["system"].strip(),
        data["user"].strip(),
        OUTPUT_SCHEMAS[name],
    )


def load_lock() -> dict[str, str]:
    return json.loads(_prompt_dir().joinpath("lock.json").read_text(encoding="utf-8"))


TEMPLATE_NAMES = tuple(OUTPUT_SCHEMAS)


def historical_templates() -> list[PromptTemplate]:
    """Every archived template version in prompts/history/."""
    history = _prompt_dir().joinpath("history")
    if not history.is_dir():
        return []
    out = []
    for entry in sorted(history.iterdir(), key=lambda e: e.name):
        if entry.name.endswith(".toml"):
            version = entry.name[: -len(".toml")]
            name = next(n for n in TEMPLATE_NAMES if version.startswith(f"{n}-"))
            out.append(load_template(name, version))
    return out
