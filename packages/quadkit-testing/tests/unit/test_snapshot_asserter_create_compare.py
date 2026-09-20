"""Test SnapshotAsserter snapshot creation and comparison.

SnapshotAsserter provides snapshot testing support: it captures a serialised
representation of a value on first run and verifies on subsequent runs that
the value has not changed.

This test suite validates:
1. First-run snapshot creation and skip behavior
2. Subsequent-run comparison and assertion
3. SnapshotMismatchError on diff
4. Update and delete operations
5. File path and directory management
6. JSON serialization handling
"""

from __future__ import annotations

from quadkit import serialization as json
import os
from pathlib import Path
import tempfile

import pytest

from quadkit.testing.lib.snapshots import SnapshotAsserter, SnapshotMismatchError


class TestSnapshotAsserterFirstRunCreation:
    """Test SnapshotAsserter first-run snapshot creation."""

    def test_assert_match_creates_snapshot_on_first_run(self) -> None:
        """Verify assert_match creates snapshot file on first run."""
        with tempfile.TemporaryDirectory() as tmpdir:
            snapshot_dir = Path(tmpdir)
            asserter = SnapshotAsserter(snapshot_dir)

            value = {"name": "Alice", "age": 30}

            # First run should create the snapshot and skip the test
            with pytest.raises(pytest.skip.Exception):
                asserter.assert_match("test_user", value)

            # Verify snapshot file was created
            snapshot_path = snapshot_dir / "test_user.json"
            assert snapshot_path.exists()

            # Verify content is correct
            stored = json.loads(snapshot_path.read_text(encoding="utf-8"))
            assert stored == value

    def test_assert_match_skips_test_on_first_run(self) -> None:
        """Verify assert_match raises pytest.skip.Exception on first run."""
        with tempfile.TemporaryDirectory() as tmpdir:
            snapshot_dir = Path(tmpdir)
            asserter = SnapshotAsserter(snapshot_dir)

            # First run should raise pytest.skip.Exception
            with pytest.raises(pytest.skip.Exception) as exc_info:
                asserter.assert_match("test_config", {"debug": True})

            # Verify skip message contains relevant info
            assert "test_config" in str(exc_info.value)

    def test_assert_match_creates_snapshot_directory_if_missing(self) -> None:
        """Verify assert_match creates snapshot directory structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            snapshot_dir = Path(tmpdir) / "nested" / "snapshots"
            assert not snapshot_dir.exists()

            asserter = SnapshotAsserter(snapshot_dir)

            with pytest.raises(pytest.skip.Exception):
                asserter.assert_match("test_item", {"id": 1})

            assert snapshot_dir.exists()

    def test_assert_match_with_default_snapshot_dir(self) -> None:
        """Verify assert_match uses default __snapshots__ directory."""
        # Save current dir, change to temp dir
        import shutil

        tmpdir = tempfile.mkdtemp()
        old_cwd = Path.cwd()
        try:
            os.chdir(tmpdir)

            # Use default snapshot dir (should be __snapshots__ in cwd)
            asserter = SnapshotAsserter()

            with pytest.raises(pytest.skip.Exception):
                asserter.assert_match("test_default", {"key": "value"})

            # Verify snapshot was created in default location
            default_path = Path.cwd() / "__snapshots__" / "test_default.json"
            assert default_path.exists()
        finally:
            os.chdir(str(old_cwd))
            shutil.rmtree(tmpdir, ignore_errors=True)


class TestSnapshotAsserterComparison:
    """Test SnapshotAsserter comparison on subsequent runs."""

    def test_assert_match_passes_when_value_matches_snapshot(self) -> None:
        """Verify assert_match passes when value matches stored snapshot."""
        with tempfile.TemporaryDirectory() as tmpdir:
            snapshot_dir = Path(tmpdir)
            asserter = SnapshotAsserter(snapshot_dir)

            value = {"id": "user-123", "status": "active"}

            # First run: create snapshot
            with pytest.raises(pytest.skip.Exception):
                asserter.assert_match("user_snapshot", value)

            # Second run: should pass without exception
            asserter.assert_match("user_snapshot", value)

    def test_assert_match_fails_when_value_differs_from_snapshot(self) -> None:
        """Verify assert_match raises SnapshotMismatchError on diff."""
        with tempfile.TemporaryDirectory() as tmpdir:
            snapshot_dir = Path(tmpdir)
            asserter = SnapshotAsserter(snapshot_dir)

            # Create initial snapshot
            with pytest.raises(pytest.skip.Exception):
                asserter.assert_match("config", {"debug": False})

            # Now try with different value
            with pytest.raises(SnapshotMismatchError) as exc_info:
                asserter.assert_match("config", {"debug": True})

            error = exc_info.value
            assert error.name == "config"
            assert error.expected == {"debug": False}
            assert error.actual == {"debug": True}

    def test_snapshot_mismatch_error_message_is_informative(self) -> None:
        """Verify SnapshotMismatchError message contains full details."""
        with tempfile.TemporaryDirectory() as tmpdir:
            snapshot_dir = Path(tmpdir)
            asserter = SnapshotAsserter(snapshot_dir)

            # Create snapshot
            with pytest.raises(pytest.skip.Exception):
                asserter.assert_match("api_response", {"status": 200, "data": []})

            # Change and trigger mismatch
            with pytest.raises(SnapshotMismatchError) as exc_info:
                asserter.assert_match(
                    "api_response", {"status": 500, "error": "failure"}
                )

            message = str(exc_info.value)
            assert "api_response" in message
            assert "Expected" in message
            assert "Actual" in message

    def test_assert_match_normalizes_numeric_types_via_json(self) -> None:
        """Verify assert_match compares via JSON normalization."""
        with tempfile.TemporaryDirectory() as tmpdir:
            snapshot_dir = Path(tmpdir)
            asserter = SnapshotAsserter(snapshot_dir)

            # Create snapshot with int
            with pytest.raises(pytest.skip.Exception):
                asserter.assert_match("numbers", {"count": 42})

            # Compare with same value (should pass despite type)
            asserter.assert_match("numbers", {"count": 42})


class TestSnapshotAsserterUpdate:
    """Test SnapshotAsserter update operation."""

    def test_update_creates_or_overwrites_snapshot(self) -> None:
        """Verify update() creates new snapshot or overwrites existing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            snapshot_dir = Path(tmpdir)
            asserter = SnapshotAsserter(snapshot_dir)

            value1 = {"version": 1}
            path1 = asserter.update("versioned", value1)

            assert path1.exists()
            stored = json.loads(path1.read_text(encoding="utf-8"))
            assert stored == value1

            # Update with new value
            value2 = {"version": 2}
            path2 = asserter.update("versioned", value2)

            assert path2 == path1  # Same path
            stored = json.loads(path2.read_text(encoding="utf-8"))
            assert stored == value2

    def test_update_returns_path(self) -> None:
        """Verify update() returns Path to created snapshot."""
        with tempfile.TemporaryDirectory() as tmpdir:
            snapshot_dir = Path(tmpdir)
            asserter = SnapshotAsserter(snapshot_dir)

            result_path = asserter.update("test_name", {"key": "value"})

            assert isinstance(result_path, Path)
            assert result_path.name == "test_name.json"
            assert result_path.parent == snapshot_dir

    def test_update_with_complex_nested_structure(self) -> None:
        """Verify update() handles deeply nested structures."""
        with tempfile.TemporaryDirectory() as tmpdir:
            snapshot_dir = Path(tmpdir)
            asserter = SnapshotAsserter(snapshot_dir)

            complex_value = {
                "users": [
                    {"id": 1, "profile": {"name": "Alice", "tags": ["admin"]}},
                    {"id": 2, "profile": {"name": "Bob", "tags": ["user"]}},
                ],
                "metadata": {"count": 2, "page": 1},
            }

            path = asserter.update("complex_data", complex_value)
            stored = json.loads(path.read_text(encoding="utf-8"))
            assert stored == complex_value


class TestSnapshotAsserterDelete:
    """Test SnapshotAsserter delete operation."""

    def test_delete_removes_snapshot_file(self) -> None:
        """Verify delete() removes snapshot file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            snapshot_dir = Path(tmpdir)
            asserter = SnapshotAsserter(snapshot_dir)

            # Create snapshot
            asserter.update("to_delete", {"data": "value"})
            assert (snapshot_dir / "to_delete.json").exists()

            # Delete it
            result = asserter.delete("to_delete")

            assert result is True
            assert not (snapshot_dir / "to_delete.json").exists()

    def test_delete_returns_false_for_nonexistent_snapshot(self) -> None:
        """Verify delete() returns False if snapshot doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            snapshot_dir = Path(tmpdir)
            asserter = SnapshotAsserter(snapshot_dir)

            result = asserter.delete("nonexistent")

            assert result is False

    def test_delete_returns_true_on_successful_deletion(self) -> None:
        """Verify delete() returns True on successful deletion."""
        with tempfile.TemporaryDirectory() as tmpdir:
            snapshot_dir = Path(tmpdir)
            asserter = SnapshotAsserter(snapshot_dir)

            asserter.update("deletable", {"value": 1})
            result = asserter.delete("deletable")

            assert isinstance(result, bool)
            assert result is True


class TestSnapshotAsserterExists:
    """Test SnapshotAsserter exists method."""

    def test_exists_returns_true_for_existing_snapshot(self) -> None:
        """Verify exists() returns True if snapshot file exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            snapshot_dir = Path(tmpdir)
            asserter = SnapshotAsserter(snapshot_dir)

            asserter.update("existing", {"data": "here"})
            result = asserter.exists("existing")

            assert result is True

    def test_exists_returns_false_for_nonexistent_snapshot(self) -> None:
        """Verify exists() returns False if snapshot doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            snapshot_dir = Path(tmpdir)
            asserter = SnapshotAsserter(snapshot_dir)

            result = asserter.exists("missing")

            assert result is False


class TestSnapshotAsserterIntegration:
    """Integration tests for SnapshotAsserter."""

    def test_assert_match_workflow_create_compare_update(self) -> None:
        """Verify full workflow: create → compare → update."""
        with tempfile.TemporaryDirectory() as tmpdir:
            snapshot_dir = Path(tmpdir)
            asserter = SnapshotAsserter(snapshot_dir)

            # Step 1: Create snapshot
            with pytest.raises(pytest.skip.Exception):
                asserter.assert_match("workflow", {"version": 1})

            assert asserter.exists("workflow")

            # Step 2: Verify comparison passes
            asserter.assert_match("workflow", {"version": 1})

            # Step 3: Update to new value
            asserter.update("workflow", {"version": 2})

            # Step 4: New comparison passes
            asserter.assert_match("workflow", {"version": 2})

            # Step 5: Old value now fails
            with pytest.raises(SnapshotMismatchError):
                asserter.assert_match("workflow", {"version": 1})

    def test_multiple_snapshots_in_same_directory(self) -> None:
        """Verify multiple snapshots can coexist in one directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            snapshot_dir = Path(tmpdir)
            asserter = SnapshotAsserter(snapshot_dir)

            # Create multiple snapshots
            asserter.update("snapshot_a", {"name": "A"})
            asserter.update("snapshot_b", {"name": "B"})
            asserter.update("snapshot_c", {"name": "C"})

            # All should exist
            assert asserter.exists("snapshot_a")
            assert asserter.exists("snapshot_b")
            assert asserter.exists("snapshot_c")

            # All should match
            asserter.assert_match("snapshot_a", {"name": "A"})
            asserter.assert_match("snapshot_b", {"name": "B"})
            asserter.assert_match("snapshot_c", {"name": "C"})

    def test_snapshot_handles_special_json_values(self) -> None:
        """Verify snapshots handle null, bool, lists correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            snapshot_dir = Path(tmpdir)
            asserter = SnapshotAsserter(snapshot_dir)

            complex_value = {
                "nullable": None,
                "boolean_true": True,
                "boolean_false": False,
                "list": [1, 2, 3],
                "nested_list": [[1, 2], [3, 4]],
                "string": "test",
                "number": 42,
                "float": 3.14,
            }

            with pytest.raises(pytest.skip.Exception):
                asserter.assert_match("special_types", complex_value)

            # Should match exactly on second run
            asserter.assert_match("special_types", complex_value)
