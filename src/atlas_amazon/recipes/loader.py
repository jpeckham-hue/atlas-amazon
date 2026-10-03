"""Load, merge, and strictly validate TOML recipes.

A recipe may `extends` one parent. The chain is merged root first: tables are
merged key by key and anything else (lists included) is replaced by the child.
`id`, `version`, `description` and `extends` are never inherited.

Validation is strict on purpose. Unknown keys, unsourced limits, unknown
checks, dangling field references and keyword weights that don't sum to 1
are load-time errors, not silent defaults.
"""

from __future__ import annotations

import math
import re
import tomllib
from collections.abc import Mapping
from datetime import date
from importlib import resources
from pathlib import Path
from types import MappingProxyType
from typing import Any
from urllib.parse import urlparse

from atlas_amazon.models import Severity, SourceRef, SourceStatus
from atlas_amazon.recipes.schema import (
    BACKEND_CHECKS,
    BACKEND_MODES,
    FIELD_KINDS,
    FIELD_LIMITS,
    KEYWORD_SIGNALS,
    KNOWN_CHECKS,
    BackendSpec,
    FieldSpec,
    Recipe,
    RuleSpec,
)

_RECIPE_ID = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_LEAF_ONLY = frozenset({"id", "extends", "version", "description"})
_TOP_LEVEL = frozenset({"sources", "fields", "rules", "backend", "scoring", "research"})
_SOURCE_KEYS = frozenset(
    {"title", "as_of", "status", "url", "marketplace", "scope", "note", "see_also"}
)
_FIELD_LIMITS = FIELD_LIMITS
_LIST_ONLY_LIMITS = frozenset({"min_count", "max_count", "item_max_chars", "item_max_bytes"})
_TEXT_ONLY_LIMITS = frozenset({"max_chars", "max_bytes"})
_FIELD_KEYS = frozenset(
    {"kind", "required", "source", "limit_sources", "description", *_FIELD_LIMITS}
)
_RULE_META = frozenset({"check", "severity", "source", "fields", "enabled", "description"})
_BACKEND_KEYS = frozenset({"field", "mode", "source", "count_spaces", "stopwords"})
_OPTIONAL_PARAMS: Mapping[str, frozenset[str]] = {"word_repetition": frozenset({"exempt"})}


# Hosts whose pages may back a `verified` source. Anything else (forums,
# blogs, tool vendors) can only appear in `see_also`.
OFFICIAL_HOSTS = frozenset(
    {
        "sellercentral.amazon.com",
        "kdp.amazon.com",
        "advertising.amazon.com",
        "developer-docs.amazon.com",
    }
)
# Official hosts serve help articles and also user forums; forum threads are
# not policy documents even when posted by Amazon staff.
_NON_POLICY_PATHS = ("/seller-forums/", "/forums/")


def is_official_policy_url(url: str) -> bool:
    parsed = urlparse(url)
    return (
        parsed.scheme == "https"
        and parsed.hostname in OFFICIAL_HOSTS
        and not any(parsed.path.startswith(p) for p in _NON_POLICY_PATHS)
    )


class RecipeError(ValueError):
    pass


def _fail(recipe_id: str, path: str, message: str) -> RecipeError:
    return RecipeError(f"recipe {recipe_id!r}: {path}: {message}")


def _deep_merge(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _builtin_dir() -> Any:
    return resources.files("atlas_amazon.recipes").joinpath("data")


def available_recipes(search_path: Path | None = None) -> list[str]:
    root = search_path if search_path is not None else _builtin_dir()
    return sorted(p.name[:-5] for p in root.iterdir() if p.name.endswith(".toml"))


def _read_raw(recipe_id: str, search_path: Path | None) -> dict[str, Any]:
    if not _RECIPE_ID.match(recipe_id):
        raise RecipeError(f"invalid recipe id {recipe_id!r}")
    root = search_path if search_path is not None else _builtin_dir()
    path = root.joinpath(f"{recipe_id}.toml")
    if not path.is_file():
        raise RecipeError(f"recipe {recipe_id!r} not found")
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise _fail(recipe_id, "<file>", f"invalid TOML: {exc}") from exc
    if raw.get("id") != recipe_id:
        raise _fail(recipe_id, "id", f"must equal the file name, got {raw.get('id')!r}")
    return raw


def _resolve_chain(recipe_id: str, search_path: Path | None) -> list[dict[str, Any]]:
    chain: list[dict[str, Any]] = []
    seen: list[str] = []
    current: str | None = recipe_id
    while current is not None:
        if current in seen:
            raise RecipeError(f"recipe inheritance cycle: {' -> '.join([*seen, current])}")
        seen.append(current)
        raw = _read_raw(current, search_path)
        chain.append(raw)
        parent = raw.get("extends")
        if parent is not None and not isinstance(parent, str):
            raise _fail(current, "extends", "must be a single recipe id")
        current = parent
    chain.reverse()
    return chain


def load_recipe(recipe_id: str, search_path: Path | None = None) -> Recipe:
    """Load a recipe by id from the built-in recipes, or from `search_path` if given."""
    chain = _resolve_chain(recipe_id, search_path)
    merged: dict[str, Any] = {}
    for raw in chain:
        merged = _deep_merge(merged, {k: v for k, v in raw.items() if k not in _LEAF_ONLY})
    return _build(chain[-1], merged, tuple(raw["id"] for raw in chain))


# ---------------------------------------------------------------------------
# Building and validation


def _table(rid: str, path: str, value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise _fail(rid, path, "must be a table")
    return value


def _check_keys(rid: str, path: str, table: Mapping[str, Any], allowed: frozenset[str]) -> None:
    unknown = sorted(set(table) - allowed)
    if unknown:
        raise _fail(rid, path, f"unknown keys {unknown}")


def _pos_int(rid: str, path: str, value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise _fail(rid, path, f"must be a positive integer, got {value!r}")
    return value


def _str_list(rid: str, path: str, value: Any) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(v, str) and v for v in value):
        raise _fail(rid, path, "must be a list of non-empty strings")
    return tuple(value)


def _source_ref(rid: str, path: str, value: Any, sources: Mapping[str, SourceRef]) -> SourceRef:
    if value not in sources:
        raise _fail(rid, path, f"unknown source {value!r}")
    return sources[value]


def _build_sources(rid: str, raw: Any) -> dict[str, SourceRef]:
    sources = {}
    for sid, entry in _table(rid, "sources", raw).items():
        path = f"sources.{sid}"
        entry = _table(rid, path, entry)
        _check_keys(rid, path, entry, _SOURCE_KEYS)
        if not isinstance(entry.get("title"), str) or not entry["title"]:
            raise _fail(rid, f"{path}.title", "required")
        as_of = entry.get("as_of")
        if not isinstance(as_of, date):
            raise _fail(rid, f"{path}.as_of", "required TOML date (YYYY-MM-DD)")
        try:
            status = SourceStatus(entry.get("status"))
        except ValueError:
            raise _fail(
                rid, f"{path}.status", f"must be one of {[s.value for s in SourceStatus]}"
            ) from None
        url = entry.get("url")
        if status is SourceStatus.VERIFIED and not (
            isinstance(url, str) and is_official_policy_url(url)
        ):
            raise _fail(rid, f"{path}.url", "verified sources need an official Amazon policy URL")
        if status is SourceStatus.UNVERIFIED and not entry.get("note"):
            raise _fail(rid, f"{path}.note", "unverified sources must explain why")
        sources[sid] = SourceRef(
            id=sid,
            title=entry["title"],
            as_of=as_of,
            status=status,
            url=url,
            marketplace=entry.get("marketplace"),
            scope=entry.get("scope"),
            note=entry.get("note"),
            see_also=_str_list(rid, f"{path}.see_also", entry.get("see_also", [])),
        )
    return sources


def _build_field(rid: str, name: str, raw: Any, sources: Mapping[str, SourceRef]) -> FieldSpec:
    path = f"fields.{name}"
    raw = _table(rid, path, raw)
    _check_keys(rid, path, raw, _FIELD_KEYS)
    kind = raw.get("kind")
    if kind not in FIELD_KINDS:
        raise _fail(rid, f"{path}.kind", f"must be one of {sorted(FIELD_KINDS)}")
    limits = {k: _pos_int(rid, f"{path}.{k}", raw[k]) for k in _FIELD_LIMITS if k in raw}
    wrong = _LIST_ONLY_LIMITS if kind == "text" else _TEXT_ONLY_LIMITS
    misplaced = sorted(set(limits) & wrong)
    if misplaced:
        raise _fail(rid, path, f"{misplaced} not valid for a {kind} field")
    if limits.get("min_count", 0) > limits.get("max_count", math.inf):
        raise _fail(rid, path, "min_count exceeds max_count")
    source = None
    if "source" in raw:
        source = _source_ref(rid, f"{path}.source", raw["source"], sources)
    limit_sources = {}
    for limit, sid in _table(rid, f"{path}.limit_sources", raw.get("limit_sources", {})).items():
        if limit not in limits:
            raise _fail(rid, f"{path}.limit_sources", f"{limit!r} is not a limit set on this field")
        limit_sources[limit] = _source_ref(rid, f"{path}.limit_sources.{limit}", sid, sources)
    if source is None and set(limits) - set(limit_sources):
        raise _fail(rid, path, "limits require a source (no limit without provenance)")
    required = raw.get("required", False)
    if not isinstance(required, bool):
        raise _fail(rid, f"{path}.required", "must be a boolean")
    return FieldSpec(
        name=name,
        kind=kind,
        required=required,
        source=source,
        limit_sources=MappingProxyType(limit_sources),
        description=raw.get("description", ""),
        **limits,
    )


def _build_rule(
    rid: str,
    rule_id: str,
    raw: Any,
    fields: Mapping[str, FieldSpec],
    sources: Mapping[str, SourceRef],
) -> RuleSpec:
    path = f"rules.{rule_id}"
    raw = _table(rid, path, raw)
    check = raw.get("check")
    if check not in KNOWN_CHECKS:
        raise _fail(rid, f"{path}.check", f"unknown check {check!r}")
    try:
        severity = Severity(raw.get("severity"))
    except ValueError:
        raise _fail(
            rid, f"{path}.severity", f"must be one of {[s.value for s in Severity]}"
        ) from None
    if "source" not in raw:
        raise _fail(rid, f"{path}.source", "every rule must cite a source")
    source = _source_ref(rid, f"{path}.source", raw["source"], sources)
    rule_fields = _str_list(rid, f"{path}.fields", raw.get("fields", []))
    if check not in BACKEND_CHECKS and not rule_fields:
        raise _fail(rid, f"{path}.fields", "required for this check")
    params = {k: v for k, v in raw.items() if k not in _RULE_META}
    _check_keys(
        rid, path, params, frozenset(KNOWN_CHECKS[check]) | _OPTIONAL_PARAMS.get(check, frozenset())
    )
    for required in KNOWN_CHECKS[check]:
        if required not in params:
            raise _fail(rid, f"{path}.{required}", "required param")
    referenced = list(rule_fields)
    if check == "backend_visible_overlap":
        referenced += _str_list(rid, f"{path}.visible_fields", params["visible_fields"])
    for name in referenced:
        if name not in fields:
            raise _fail(rid, path, f"references unknown field {name!r}")
    if check in ("word_repetition", "combined_length"):
        key = "max_repeats" if check == "word_repetition" else "max_chars"
        _pos_int(rid, f"{path}.{key}", params[key])
    if check == "prohibited_terms":
        _str_list(rid, f"{path}.terms", params["terms"])
    if check == "word_repetition" and "exempt" in params:
        _str_list(rid, f"{path}.exempt", params["exempt"])
    if check == "disallowed_characters" and not (
        isinstance(params["characters"], str) and params["characters"]
    ):
        raise _fail(rid, f"{path}.characters", "must be a non-empty string")
    enabled = raw.get("enabled", True)
    if not isinstance(enabled, bool):
        raise _fail(rid, f"{path}.enabled", "must be a boolean")
    return RuleSpec(
        id=rule_id,
        check=check,
        severity=severity,
        source=source,
        fields=rule_fields,
        params=MappingProxyType(params),
        enabled=enabled,
        description=raw.get("description", ""),
    )


def _build_backend(
    rid: str, raw: Any, fields: Mapping[str, FieldSpec], sources: Mapping[str, SourceRef]
) -> BackendSpec | None:
    if raw is None:
        return None
    raw = _table(rid, "backend", raw)
    _check_keys(rid, "backend", raw, _BACKEND_KEYS)
    name = raw.get("field")
    if name not in fields:
        raise _fail(rid, "backend.field", f"unknown field {name!r}")
    spec = fields[name]
    mode = raw.get("mode")
    if mode not in BACKEND_MODES:
        raise _fail(rid, "backend.mode", f"must be one of {sorted(BACKEND_MODES)}")
    if mode == "bytes" and (spec.kind != "text" or spec.max_bytes is None):
        raise _fail(rid, "backend", "bytes mode needs a text field with max_bytes")
    if mode == "slots" and (
        spec.kind != "list" or spec.max_count is None or spec.item_max_chars is None
    ):
        raise _fail(
            rid, "backend", "slots mode needs a list field with max_count and item_max_chars"
        )
    count_spaces = raw.get("count_spaces", True)
    if not isinstance(count_spaces, bool):
        raise _fail(rid, "backend.count_spaces", "must be a boolean")
    return BackendSpec(
        field_name=name,
        mode=mode,
        source=_source_ref(rid, "backend.source", raw.get("source"), sources),
        count_spaces=count_spaces,
        stopwords=_str_list(rid, "backend.stopwords", raw.get("stopwords", [])),
    )


def _weights(rid: str, path: str, raw: Any) -> dict[str, float]:
    result = {}
    for key, value in _table(rid, path, raw).items():
        if isinstance(value, bool) or not isinstance(value, int | float) or value < 0:
            raise _fail(rid, f"{path}.{key}", "must be a non-negative number")
        result[key] = float(value)
    return result


def _build(leaf: Mapping[str, Any], merged: Mapping[str, Any], lineage: tuple[str, ...]) -> Recipe:
    rid = leaf["id"]
    _check_keys(rid, "<top>", merged, _TOP_LEVEL)
    version = leaf.get("version")
    if not isinstance(version, str) or not version:
        raise _fail(rid, "version", "required")

    sources = _build_sources(rid, merged.get("sources", {}))
    fields = {
        name: _build_field(rid, name, raw, sources)
        for name, raw in _table(rid, "fields", merged.get("fields", {})).items()
    }
    if not fields:
        raise _fail(rid, "fields", "a recipe must define at least one field")
    rules = {
        rule_id: _build_rule(rid, rule_id, raw, fields, sources)
        for rule_id, raw in _table(rid, "rules", merged.get("rules", {})).items()
    }
    backend = _build_backend(rid, merged.get("backend"), fields, sources)
    if backend is None and any(r.check in BACKEND_CHECKS for r in rules.values()):
        raise _fail(rid, "rules", "backend checks require a [backend] section")

    scoring = _table(rid, "scoring", merged.get("scoring", {}))
    _check_keys(rid, "scoring", scoring, frozenset({"keyword", "coverage"}))
    keyword_weights = _weights(rid, "scoring.keyword", scoring.get("keyword", {}))
    if set(keyword_weights) != set(KEYWORD_SIGNALS):
        raise _fail(rid, "scoring.keyword", f"must define exactly {list(KEYWORD_SIGNALS)}")
    if not math.isclose(sum(keyword_weights.values()), 1.0, abs_tol=1e-9):
        raise _fail(rid, "scoring.keyword", "weights must sum to 1")
    coverage_weights = _weights(rid, "scoring.coverage", scoring.get("coverage", {}))
    unknown = sorted(set(coverage_weights) - set(fields))
    if unknown:
        raise _fail(rid, "scoring.coverage", f"unknown fields {unknown}")
    if not any(w > 0 for w in coverage_weights.values()):
        raise _fail(rid, "scoring.coverage", "at least one weight must be positive")

    research = _table(rid, "research", merged.get("research", {}))
    _check_keys(rid, "research", research, frozenset({"priorities"}))
    priorities = _str_list(rid, "research.priorities", research.get("priorities", []))

    return Recipe(
        id=rid,
        version=version,
        description=leaf.get("description", ""),
        lineage=lineage,
        fields=MappingProxyType(fields),
        rules=MappingProxyType(rules),
        backend=backend,
        keyword_weights=MappingProxyType(keyword_weights),
        coverage_weights=MappingProxyType(coverage_weights),
        research_priorities=priorities,
        sources=MappingProxyType(sources),
    )
