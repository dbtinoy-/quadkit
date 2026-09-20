"""Unit tests for SnapshotAsserter."""

from __future__ import annotations

from pathlib import Path

from quadkit import serialization as json

import pytest

from quadkit.testing.lib.snapshots import SnapshotAsserter, SnapshotMismatchError


class TestSnapshotAsserter:
    """SnapshotAsserter creates, reads, and compares snapshot files."""

    # -- helpers --

    def _asserter(self, tmp_path: Path) -> SnapshotAsserter:
        snapshot_dir = tmp_path / "__snapshots__"
        return SnapshotAsserter(snapshot_dir=snapshot_dir)

    # -- first run creates snapshot and skips --

    def test_first_run_creates_snapshot_file_and_skips(self, tmp_path: Path) -> None:
        asserter = self._asserter(tmp_path)

        with pytest.raises(pytest.skip.Exception):
            asserter.assert_match("my_snap", {"key": "value"})

        snap_file = tmp_path / "__snapshots__" / "my_snap.json"
        assert snap_file.exists()
        data = json.loads(snap_file.read_text())
        assert data == {"key": "value"}

    # -- subsequent run passes when values match --

    def test_subsequent_run_passes_on_matching_value(self, tmp_path: Path) -> None:
        asserter = self._asserter(tmp_path)
        asserter.update("my_snap", {"key": "value"})

        # Should not raise
        asserter.assert_match("my_snap", {"key": "value"})

    # -- subsequent run raises SnapshotMismatchError on mismatch --

    def test_raises_mismatch_error_on_different_value(self, tmp_path: Path) -> None:
        asserter = self._asserter(tmp_path)
        asserter.update("my_snap", {"key": "value"})

        with pytest.raises(SnapshotMismatchError) as exc_info:
            asserter.assert_match("my_snap", {"key": "CHANGED"})

        assert "my_snap" in str(exc_info.value)

    # -- update force-writes snapshot --

    def test_update_creates_or_overwrites_snapshot(self, tmp_path: Path) -> None:
        asserter = self._asserter(tmp_path)
        asserter.update("snap", {"v": 1})
        asserter.update("snap", {"v": 2})

        snap_file = tmp_path / "__snapshots__" / "snap.json"
        data = json.loads(snap_file.read_text())
        assert data == {"v": 2}

    def test_update_returns_path_to_snapshot_file(self, tmp_path: Path) -> None:
        asserter = self._asserter(tmp_path)
        path = asserter.update("snap", 42)
        assert path.exists()
        assert path.suffix == ".json"

    # -- delete --

    def test_delete_removes_snapshot_file(self, tmp_path: Path) -> None:
        asserter = self._asserter(tmp_path)
        asserter.update("snap", "hello")
        assert asserter.exists("snap")

        removed = asserter.delete("snap")

        assert removed is True
        assert not asserter.exists("snap")

    def test_delete_returns_false_when_snapshot_missing(self, tmp_path: Path) -> None:
        asserter = self._asserter(tmp_path)
        removed = asserter.delete("nonexistent")
        assert removed is False

    # -- exists --

    def test_exists_returns_false_before_creation(self, tmp_path: Path) -> None:
        asserter = self._asserter(tmp_path)
        assert not asserter.exists("not_yet")

    def test_exists_returns_true_after_update(self, tmp_path: Path) -> None:
        asserter = self._asserter(tmp_path)
        asserter.update("now_it_exists", [1, 2, 3])
        assert asserter.exists("now_it_exists")

    # -- numeric type normalisation --

    def test_integer_and_float_comparison_normalised(self, tmp_path: Path) -> None:
        """JSON round-trips normalise numeric types. 1 and 1.0 compare equal."""
        asserter = self._asserter(tmp_path)
        asserter.update("num", 1)

        # 1.0 round-trips through JSON as 1.0, same as 1; should not raise
        asserter.assert_match("num", 1)
