"""JSON-compatible, deeply immutable values.

Evidence payloads have to survive a JSONL round trip unchanged, so they are
restricted to JSON types and frozen all the way down: mappings become
read-only proxies and lists become tuples. `thaw` reverses this for
serialization.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from types import MappingProxyType
from typing import Any


def freeze(value: Any, path: str = "$") -> Any:
    """Validate that `value` is JSON-compatible and return a deeply immutable copy."""
    if value is None or isinstance(value, bool | str | int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{path}: non-finite float {value!r} is not JSON-compatible")
        return value
    if isinstance(value, Mapping):
        frozen = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError(f"{path}: mapping keys must be str, got {type(key).__name__}")
            frozen[key] = freeze(item, f"{path}.{key}")
        return MappingProxyType(frozen)
    if isinstance(value, list | tuple):
        return tuple(freeze(item, f"{path}[{i}]") for i, item in enumerate(value))
    raise TypeError(f"{path}: {type(value).__name__} is not JSON-compatible")


def thaw(value: Any) -> Any:
    """Plain dict/list copy of a frozen value, ready for `json.dumps`."""
    if isinstance(value, Mapping):
        return {key: thaw(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [thaw(item) for item in value]
    return value


def canonical_json(value: Any) -> str:
    """Deterministic JSON: sorted keys, no insignificant whitespace, UTF-8 text."""
    return json.dumps(
        thaw(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )
