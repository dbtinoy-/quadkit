"""Tests for db query builder types."""

from quadkit.sql.query.sql_types import (
    ConflictAction,
    JoinType,
    LockMode,
    SetOperationType,
)


class TestJoinType:
    """Tests for JoinType enum."""

    def test_join_type_values(self) -> None:
        """Test JoinType enum values."""
        assert JoinType.INNER.value == "INNER"
        assert JoinType.LEFT.value == "LEFT"
        assert JoinType.RIGHT.value == "RIGHT"
        assert JoinType.FULL.value == "FULL"

    def test_join_type_members(self) -> None:
        """Test JoinType has expected members."""
        members = list(JoinType)
        assert len(members) == 4


class TestConflictAction:
    """Tests for ConflictAction enum."""

    def test_conflict_action_values(self) -> None:
        """Test ConflictAction enum values."""
        assert ConflictAction.DO_NOTHING.value == "DO NOTHING"
        assert ConflictAction.DO_UPDATE.value == "DO UPDATE"

    def test_conflict_action_members(self) -> None:
        """Test ConflictAction has expected members."""
        members = list(ConflictAction)
        assert len(members) == 2


class TestLockMode:
    """Tests for LockMode enum."""

    def test_lock_mode_values(self) -> None:
        """Test LockMode enum values."""
        assert LockMode.FOR_UPDATE.value == "FOR UPDATE"
        assert LockMode.FOR_SHARE.value == "FOR SHARE"
        assert LockMode.FOR_NO_KEY_UPDATE.value == "FOR NO KEY UPDATE"
        assert LockMode.FOR_KEY_SHARE.value == "FOR KEY SHARE"

    def test_lock_mode_members(self) -> None:
        """Test LockMode has expected members."""
        members = list(LockMode)
        assert len(members) == 4


class TestSetOperationType:
    """Tests for SetOperationType enum."""

    def test_set_operation_type_values(self) -> None:
        """Test SetOperationType enum values."""
        assert SetOperationType.UNION.value == "UNION"
        assert SetOperationType.UNION_ALL.value == "UNION ALL"
        assert SetOperationType.INTERSECT.value == "INTERSECT"
        assert SetOperationType.EXCEPT.value == "EXCEPT"

    def test_set_operation_type_members(self) -> None:
        """Test SetOperationType has expected members."""
        members = list(SetOperationType)
        assert len(members) == 4
