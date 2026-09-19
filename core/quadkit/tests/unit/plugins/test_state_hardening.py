"""Error-path tests for plugin state persistence."""

from __future__ import annotations

from pathlib import Path

import pytest

from quadkit.contracts.exceptions.infra import InfrastructureError
from quadkit.plugins.exceptions import PluginStateError


def test_plugin_state_error_is_an_infrastructure_error() -> None:
    assert issubclass(PluginStateError, InfrastructureError)


def test_plugin_state_error_carries_structured_message(tmp_path: Path) -> None:
    err = PluginStateError("cannot write plugin state", path=str(tmp_path / "p.json"))
    assert "cannot write plugin state" in str(err)


import json

from quadkit.plugins.state import (
    _STATE_SCHEMA_VERSION,
    load_disabled,
    save_disabled,
    update_disabled,
)


def test_save_writes_versioned_schema(tmp_path: Path) -> None:
    path = tmp_path / "plugins.json"
    save_disabled({"alpha"}, path)
    data = json.loads(path.read_text())
    assert data == {"version": _STATE_SCHEMA_VERSION, "disabled": ["alpha"]}


def test_load_reads_legacy_unversioned_file(tmp_path: Path) -> None:
    path = tmp_path / "plugins.json"
    path.write_text(json.dumps({"disabled": ["legacy"]}))
    assert load_disabled(path) == {"legacy"}


def test_load_reads_versioned_file(tmp_path: Path) -> None:
    path = tmp_path / "plugins.json"
    path.write_text(json.dumps({"version": 1, "disabled": ["a", "b"]}))
    assert load_disabled(path) == {"a", "b"}


def test_load_invalid_disabled_shape_returns_empty_set(tmp_path: Path) -> None:
    path = tmp_path / "plugins.json"
    path.write_text(json.dumps({"version": 1, "disabled": "not-a-list"}))
    assert load_disabled(path) == set()


def test_corrupt_file_is_backed_up_and_fails_open(tmp_path: Path) -> None:
    path = tmp_path / "plugins.json"
    path.write_text("{not valid json")
    assert load_disabled(path) == set()
    backups = list(tmp_path.glob("plugins.json.corrupt-*"))
    assert len(backups) == 1
    assert backups[0].read_text() == "{not valid json"


def test_save_failure_raises_plugin_state_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "plugins.json"

    def _broken_replace(*args: object, **kwargs: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr("os.replace", _broken_replace)
    with pytest.raises(PluginStateError):
        save_disabled({"alpha"}, path)


def test_save_never_leaves_temp_file_behind(tmp_path: Path) -> None:
    path = tmp_path / "plugins.json"
    save_disabled({"alpha"}, path)
    save_disabled({"beta"}, path)
    assert list(tmp_path.glob("*.tmp*")) == []
    assert load_disabled(path) == {"beta"}


def test_update_disabled_merges_atomically(tmp_path: Path) -> None:
    path = tmp_path / "plugins.json"
    save_disabled({"alpha"}, path)
    result = update_disabled(lambda current: current | {"beta"}, path)
    assert result == {"alpha", "beta"}
    assert load_disabled(path) == {"alpha", "beta"}


def test_concurrent_updates_do_not_lose_entries(tmp_path: Path) -> None:
    path = tmp_path / "plugins.json"
    save_disabled(set(), path)
    import threading

    errors: list[BaseException] = []

    def worker(name: str) -> None:
        try:
            update_disabled(lambda current: current | {name}, path)
        except BaseException as exc:  # pragma: no cover
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(str(i),)) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(10)
    assert not errors
    assert load_disabled(path) == {"0", "1", "2", "3"}


def test_load_rejects_unsupported_schema_version_and_preserves_file(
    tmp_path: Path,
) -> None:
    path = tmp_path / "plugins.json"
    path.write_text(json.dumps({"version": 99, "disabled": ["future"]}))
    assert load_disabled(path) == set()
    backups = list(tmp_path.glob("plugins.json.corrupt-*"))
    assert len(backups) == 1
    assert json.loads(backups[0].read_text()) == {
        "version": 99,
        "disabled": ["future"],
    }


def test_load_rejects_non_integer_schema_version(tmp_path: Path) -> None:
    path = tmp_path / "plugins.json"
    path.write_text(json.dumps({"version": "v1", "disabled": ["x"]}))
    assert load_disabled(path) == set()
    backups = list(tmp_path.glob("plugins.json.corrupt-*"))
    assert len(backups) == 1
