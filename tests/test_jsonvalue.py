import math
from types import MappingProxyType

import pytest

from atlas_amazon.jsonvalue import canonical_json, freeze, thaw


def test_freeze_is_deep_and_immutable():
    frozen = freeze({"a": [1, {"b": [2, 3]}], "c": None})
    assert isinstance(frozen, MappingProxyType)
    assert frozen["a"] == (1, MappingProxyType({"b": (2, 3)}))
    with pytest.raises(TypeError):
        frozen["c"] = 1  # type: ignore[index]
    with pytest.raises(TypeError):
        frozen["a"][1]["b"] = ()  # type: ignore[index]


def test_freeze_copies_input():
    source = {"items": [1, 2]}
    frozen = freeze(source)
    source["items"].append(3)
    assert frozen["items"] == (1, 2)


@pytest.mark.parametrize(
    ("value", "error"),
    [
        (math.nan, ValueError),
        (math.inf, ValueError),
        ({1: "x"}, TypeError),
        ({"s": {1, 2}}, TypeError),
        (b"bytes", TypeError),
        (object(), TypeError),
    ],
)
def test_freeze_rejects_non_json(value, error):
    with pytest.raises(error):
        freeze(value)


def test_freeze_error_names_the_path():
    with pytest.raises(TypeError, match=r"\$\.a\[1\]"):
        freeze({"a": [1, {2, 3}]})


def test_thaw_round_trip():
    original = {"a": [1, {"b": [True, None, 1.5, "é"]}]}
    assert thaw(freeze(original)) == original


def test_canonical_json_is_order_independent_and_compact():
    assert canonical_json({"b": 1, "a": [1, 2]}) == '{"a":[1,2],"b":1}'
    assert canonical_json(freeze({"a": [1, 2], "b": 1})) == canonical_json({"b": 1, "a": [1, 2]})
    assert canonical_json({"k": "café"}) == '{"k":"café"}'
