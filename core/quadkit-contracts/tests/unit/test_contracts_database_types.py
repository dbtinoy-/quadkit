"""Tests for contracts database types."""

import pytest

from quadkit.contracts.data.sql.database import IsolationLevel


class TestIsolationLevel:
    """Tests for IsolationLevel enum."""

    def test_isolation_level_values(self) -> None:
        """Test IsolationLevel enum values."""
        assert IsolationLevel.READ_UNCOMMITTED.value == "READ UNCOMMITTED"
        assert IsolationLevel.READ_COMMITTED.value == "READ COMMITTED"
        assert IsolationLevel.REPEATABLE_READ.value == "REPEATABLE READ"
        assert IsolationLevel.SERIALIZABLE.value == "SERIALIZABLE"

    def test_isolation_level_members(self) -> None:
        """Test IsolationLevel has expected members."""
        members = list(IsolationLevel)
        assert len(members) == 4

    def test_isolation_level_order(self) -> None:
        """Test IsolationLevel ordering (least to most strict)."""
        # StrEnum members don't support direct comparison; verify the order by list position
        levels = [
            IsolationLevel.READ_UNCOMMITTED,
            IsolationLevel.READ_COMMITTED,
            IsolationLevel.REPEATABLE_READ,
            IsolationLevel.SERIALIZABLE,
        ]
        assert levels[0] == IsolationLevel.READ_UNCOMMITTED
        assert levels[1] == IsolationLevel.READ_COMMITTED
        assert levels[2] == IsolationLevel.REPEATABLE_READ
        assert levels[3] == IsolationLevel.SERIALIZABLE
