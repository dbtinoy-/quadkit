"""Snapshot testing support for Quadkit test suites.

Snapshot testing captures a serialised representation of a value on first run
and verifies on subsequent runs that the value has not changed.  This is
particularly useful for:

- API response regression testing
- Complex domain object shape verification
- Catching unintended breaking changes in serialised output

Usage::

    def test_user_response(snapshot):
        user = {"id": "abc", "name": "Alice"}
        snapshot.assert_match("user_response", user)
        # First run: snapshot file is created; test is skipped.
        # Subsequent runs: value is compared to the stored snapshot.

The default snapshot directory is a ``__snapshots__`` folder adjacent to the
test file.  Pass an explicit *snapshot_dir* to override.

To regenerate snapshots after an intentional change, delete the relevant
``.json`` file (or run with ``--update-snapshots`` when the pytest plugin is
enabled).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from quadkit import serialization as json


class SnapshotMismatchError(AssertionError):
    """Raised when a value does not match the stored snapshot."""

    _code: str = "QK_ERR_TEST_012"

    def __init__(self, name: str, expected: Any, actual: Any) -> None:
        self.name = name
        self.expected = expected
        self.actual = actual
        expected_str = json.dumps(expected, indent=2, default=str).decode("utf-8")
        actual_str = json.dumps(actual, indent=2, default=str).decode("utf-8")
        super().__init__(
            f"Snapshot mismatch for '{name}'.\n"
            f"Expected: {expected_str}\n"
            f"Actual:   {actual_str}\n"
            f"To update, delete the snapshot file or call snapshot.update('{name}', value)."
        )


class SnapshotAsserter:
    """Assert that a value matches a stored snapshot.

    On first run (no snapshot file exists), the current value is persisted to
    disk and the test is *skipped* via ``pytest.skip``.  On subsequent runs the
    value is compared to the stored snapshot and the test fails if they differ.

    Args:
        snapshot_dir: Directory where snapshot files are stored.  Defaults
            to a ``__snapshots__`` subdirectory of the current working
            directory.

    Example::

        asserter = SnapshotAsserter(Path("tests/__snapshots__"))
        asserter.assert_match("create_user_response", response_body)
    """

    def __init__(self, snapshot_dir: Path | None = None) -> None:
        self._dir = snapshot_dir or Path.cwd() / "__snapshots__"

    def _path(self, name: str) -> Path:
        return self._dir / f"{name}.json"

    def assert_match(self, name: str, value: Any) -> None:
        """Assert *value* matches the stored snapshot for *name*.

        Creates the snapshot and skips the test on first call.

        Args:
            name: Unique snapshot identifier (used as the filename stem).
            value: The value to compare.  Must be JSON-serialisable.

        Raises:
            SnapshotMismatchError: If the value does not match the stored snapshot.
        """
        snapshot_path = self._path(name)
        if not snapshot_path.exists():
            self.update(name, value)
            pytest.skip(
                f"Snapshot '{name}' created at {snapshot_path}. "
                "Re-run the test to assert."
            )

        expected = json.loads(snapshot_path.read_text(encoding="utf-8"))
        # Normalise via JSON round-trip so numeric types compare correctly.
        actual = json.loads(json.dumps(value, default=str))
        if actual != expected:
            raise SnapshotMismatchError(name, expected, actual)

    def update(self, name: str, value: Any) -> Path:
        """Persist *value* as the stored snapshot for *name*.

        Args:
            name: Unique snapshot identifier.
            value: The value to store.

        Returns:
            Path to the written snapshot file.
        """
        snapshot_path = self._path(name)
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        serialized = json.dumps(value, indent=2, default=str)
        # Handle both bytes and string serialization
        content = (
            serialized.decode("utf-8") if isinstance(serialized, bytes) else serialized
        )
        snapshot_path.write_text(content + "\n", encoding="utf-8")
        return snapshot_path

    def delete(self, name: str) -> bool:
        """Delete the snapshot file for *name*.

        Returns:
            ``True`` if the file existed and was deleted; ``False`` otherwise.
        """
        snapshot_path = self._path(name)
        if snapshot_path.exists():
            snapshot_path.unlink()
            return True
        return False

    def exists(self, name: str) -> bool:
        """Return ``True`` if a snapshot for *name* exists on disk."""
        return self._path(name).exists()
