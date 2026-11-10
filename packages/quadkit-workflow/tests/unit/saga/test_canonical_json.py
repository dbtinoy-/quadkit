"""Unit tests for canonical JSON bytes utility."""
from __future__ import annotations

import pytest

from quadkit.workflow.saga.canonical_json import canonical_json_bytes


class TestCanonicalJson:
    def test_sorts_keys(self):
        result = canonical_json_bytes({"b": 2, "a": 1})
        assert result == b'{"a":1,"b":2}'

    def test_compact_no_spaces(self):
        result = canonical_json_bytes({"a": [1, 2, 3]})
        assert result == b'{"a":[1,2,3]}'

    def test_nested_objects(self):
        result = canonical_json_bytes({"outer": {"b": 2, "a": 1}})
        assert result == b'{"outer":{"a":1,"b":2}}'

    def test_deterministic(self):
        a = canonical_json_bytes({"z": 9, "y": {"x": 1, "w": 2}})
        b = canonical_json_bytes({"z": 9, "y": {"x": 1, "w": 2}})
        assert a == b
