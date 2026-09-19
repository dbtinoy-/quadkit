"""Tests for the JSON serialization backend (orjson with stdlib fallback)."""

from __future__ import annotations

import datetime
from decimal import Decimal
import uuid

import pytest

from quadkit.serialization import loads as stdlib_loads
from quadkit.serialization.backends import json as json_backend


def test_backend_name_is_orjson_or_stdlib() -> None:
    assert json_backend.JSON_BACKEND in {"orjson", "stdlib"}


def test_dumps_returns_bytes() -> None:
    out = json_backend.dumps({"a": 1})
    assert isinstance(out, bytes)
    assert stdlib_loads(out) == {"a": 1}


def test_roundtrip_structures() -> None:
    data = {"list": [1, "two", 3.5], "nested": {"ok": True}, "none": None}
    assert json_backend.loads(json_backend.dumps(data)) == data


def test_dumps_str_and_loads_str() -> None:
    text = json_backend.dumps_str({"a": [1, 2]})
    assert isinstance(text, str)
    assert json_backend.loads_str(text) == {"a": [1, 2]}


def test_loads_accepts_str_input() -> None:
    assert json_backend.loads('{"a": 1}') == {"a": 1}


def test_non_string_keys() -> None:
    out = json_backend.dumps({1: "one", 2: "two"})
    assert stdlib_loads(out) == {"1": "one", "2": "two"}


def test_sort_keys_option() -> None:
    data = {"b": 1, "a": 2}
    out = json_backend.dumps(data, sort_keys=True).decode()
    assert out.index('"a"') < out.index('"b"')


def test_datetime_uuid_decimal_via_default_encoder() -> None:
    stamp = datetime.datetime(2026, 1, 2, 3, 4, 5)
    uid = uuid.uuid4()
    dec = Decimal("10.50")

    out = json_backend.dumps({"t": stamp, "u": uid, "d": dec})
    text = out.decode()
    assert "2026-01-02" in text
    assert str(uid) in text
    assert "10.5" in text


def test_nested_exotic_types() -> None:
    out = json_backend.loads(
        json_backend.dumps({"items": [{"v": Decimal("1.5")}]}),
    )
    assert out["items"][0]["v"] in (1.5, "1.5")


def test_compact_separators_consistency() -> None:
    # Both backends emit compact JSON (no spaces).
    out = json_backend.dumps({"a": 1, "b": 2}).decode()
    assert ": " not in out
    assert ", " not in out


def test_empty_containers() -> None:
    assert json_backend.loads(json_backend.dumps({})) == {}
    assert json_backend.loads(json_backend.dumps([])) == []


def test_invalid_json_raises() -> None:
    with pytest.raises(ValueError, match=r"unexpected character|Expecting property"):
        json_backend.loads("{not json")
