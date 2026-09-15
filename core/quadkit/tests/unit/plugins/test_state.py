"""Tests for quadkit.plugins.state — boot-readable disabled-plugin file mirror."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from quadkit.plugins.state import load_disabled, save_disabled


def test_load_disabled_missing_file_returns_empty_set(tmp_path: Path) -> None:
    path = tmp_path / "plugins.json"
    assert load_disabled(path) == set()


def test_save_then_load_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "plugins.json"
    save_disabled({"relay-gateway", "other-plugin"}, path)
    assert load_disabled(path) == {"relay-gateway", "other-plugin"}


def test_save_creates_parent_directories(tmp_path: Path) -> None:
    path = tmp_path / "a" / "b" / "plugins.json"
    save_disabled({"x"}, path)
    assert path.exists()


def test_load_disabled_malformed_json_returns_empty_set(tmp_path: Path) -> None:
    path = tmp_path / "plugins.json"
    path.write_text("not json{{{")
    assert load_disabled(path) == set()


def test_save_disabled_writes_sorted_list(tmp_path: Path) -> None:
    path = tmp_path / "plugins.json"
    save_disabled({"zeta", "alpha"}, path)
    data = json.loads(path.read_text())
    assert data == {"version": 1, "disabled": ["alpha", "zeta"]}


def test_load_disabled_uses_env_var_when_no_path_given(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "env-plugins.json"
    save_disabled({"from-env"}, path)
    monkeypatch.setenv("QUADKIT_PLUGINS_STATE_PATH", str(path))
    assert load_disabled() == {"from-env"}
