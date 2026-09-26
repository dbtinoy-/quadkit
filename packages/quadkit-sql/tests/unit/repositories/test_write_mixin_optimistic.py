"""Unit tests for _WriteMixin optimistic locking behavior."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.sql.exceptions import OptimisticLockError, RepositoryError
from quadkit.sql.repositories.generic_repository import GenericRepository

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _Entity:
    """Minimal entity with version field."""

    def __init__(self, id: int, name: str, version: int = 0) -> None:
        self.id = id
        self.name = name
        self.version = version


def _make_update_result(success: bool, affected_rows: int) -> MagicMock:
    result = MagicMock()
    result.success = success
    result.affected_rows = affected_rows
    result.error_message = None
    return result


def _make_repo(mock_provider: MagicMock) -> GenericRepository[_Entity, int]:
    return GenericRepository(
        provider=mock_provider,
        table_name="entities",
        entity_class=_Entity,
        key_field="id",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestWriteMixinOptimisticLock:
    """Tests for optimistic locking in _WriteMixin.update()."""

    @pytest.fixture
    def mock_provider(self) -> MagicMock:
        """Return a mock database provider."""
        provider = MagicMock()
        provider.execute_update = AsyncMock()
        return provider

    @pytest.fixture
    def repo(self, mock_provider: MagicMock) -> GenericRepository[_Entity, int]:
        """Return a repository backed by the mock provider."""
        return _make_repo(mock_provider)

    # --- check_version=False (explicit opt-out) ---

    @pytest.mark.asyncio
    async def test_standard_update_success(
        self,
        repo: GenericRepository[_Entity, int],
        mock_provider: MagicMock,
    ) -> None:
        """Standard update (no version check) succeeds when provider reports success."""
        mock_provider.execute_update.return_value = _make_update_result(
            success=True, affected_rows=1
        )
        entity = _Entity(id=1, name="Alice", version=3)

        result = await repo.update(entity, check_version=False)

        assert result is entity
        mock_provider.execute_update.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_standard_update_does_not_use_version_in_where_clause(
        self,
        repo: GenericRepository[_Entity, int],
        mock_provider: MagicMock,
    ) -> None:
        """Standard update WHERE clause must NOT contain 'version'."""
        mock_provider.execute_update.return_value = _make_update_result(
            success=True, affected_rows=1
        )
        entity = _Entity(id=1, name="Alice", version=5)

        await repo.update(entity, check_version=False)

        positional = mock_provider.execute_update.call_args.args
        # Third positional argument is the WHERE clause string
        where_clause: str = positional[2]
        assert "version" not in where_clause.lower()

    # --- check_version=True ---

    @pytest.mark.asyncio
    async def test_versioned_update_success_increments_version(
        self,
        repo: GenericRepository[_Entity, int],
        mock_provider: MagicMock,
    ) -> None:
        """Successful versioned update must increment entity.version by 1."""
        mock_provider.execute_update.return_value = _make_update_result(
            success=True, affected_rows=1
        )
        entity = _Entity(id=1, name="Alice", version=2)

        result = await repo.update(entity, check_version=True)

        assert result is entity
        assert entity.version == 3

    @pytest.mark.asyncio
    async def test_versioned_update_includes_version_in_where_clause(
        self,
        repo: GenericRepository[_Entity, int],
        mock_provider: MagicMock,
    ) -> None:
        """Versioned update WHERE clause must include 'version = ?'."""
        mock_provider.execute_update.return_value = _make_update_result(
            success=True, affected_rows=1
        )
        entity = _Entity(id=1, name="Alice", version=4)

        await repo.update(entity, check_version=True)

        positional = mock_provider.execute_update.call_args.args
        where_clause: str = positional[2]
        assert "version" in where_clause.lower()

    @pytest.mark.asyncio
    async def test_versioned_update_zero_rows_raises_optimistic_lock_error(
        self,
        repo: GenericRepository[_Entity, int],
        mock_provider: MagicMock,
    ) -> None:
        """0 affected rows must raise OptimisticLockError."""
        mock_provider.execute_update.return_value = _make_update_result(
            success=True, affected_rows=0
        )
        entity = _Entity(id=42, name="Bob", version=7)

        with pytest.raises(OptimisticLockError) as exc_info:
            await repo.update(entity, check_version=True)

        err = exc_info.value
        assert err.entity_type == "_Entity"
        assert err.entity_id == 42
        assert err.expected_version == 7

    @pytest.mark.asyncio
    async def test_versioned_update_failure_result_raises_optimistic_lock_error(
        self,
        repo: GenericRepository[_Entity, int],
        mock_provider: MagicMock,
    ) -> None:
        """Provider failure (success=False) must raise OptimisticLockError."""
        mock_provider.execute_update.return_value = _make_update_result(
            success=False, affected_rows=1
        )
        entity = _Entity(id=99, name="Carol", version=1)

        with pytest.raises(OptimisticLockError):
            await repo.update(entity, check_version=True)

    @pytest.mark.asyncio
    async def test_versioned_update_entity_without_version_raises_value_error(
        self,
        repo: GenericRepository[_Entity, int],
        mock_provider: MagicMock,
    ) -> None:
        """Entity without 'version' attribute must raise ValueError."""

        class _NoVersionEntity:
            def __init__(self) -> None:
                self.id = 1
                self.name = "x"

        entity = _NoVersionEntity()

        with pytest.raises(ValueError, match="version"):
            await repo.update(entity, check_version=True)  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_versioned_update_non_int_version_raises_type_error(
        self,
        repo: GenericRepository[_Entity, int],
        mock_provider: MagicMock,
    ) -> None:
        """Non-integer 'version' attribute must raise TypeError."""
        entity = _Entity(id=1, name="Dave", version=0)
        entity.version = "not-an-int"  # type: ignore[assignment]

        with pytest.raises(TypeError, match="int"):
            await repo.update(entity, check_version=True)

    @pytest.mark.asyncio
    async def test_versioned_update_version_not_incremented_on_failure(
        self,
        repo: GenericRepository[_Entity, int],
        mock_provider: MagicMock,
    ) -> None:
        """entity.version must NOT be incremented when the lock check fails."""
        mock_provider.execute_update.return_value = _make_update_result(
            success=True, affected_rows=0
        )
        entity = _Entity(id=1, name="Eve", version=3)

        with pytest.raises(OptimisticLockError):
            await repo.update(entity, check_version=True)

        assert entity.version == 3  # unchanged

    @pytest.mark.asyncio
    async def test_optimistic_lock_error_message_is_descriptive(
        self,
        repo: GenericRepository[_Entity, int],
        mock_provider: MagicMock,
    ) -> None:
        """OptimisticLockError message must name entity, id, and expected version."""
        mock_provider.execute_update.return_value = _make_update_result(
            success=True, affected_rows=0
        )
        entity = _Entity(id=7, name="Frank", version=5)

        with pytest.raises(OptimisticLockError) as exc_info:
            await repo.update(entity, check_version=True)

        msg = str(exc_info.value)
        assert "_Entity" in msg
        assert "7" in msg
        assert "5" in msg

    @pytest.mark.asyncio
    async def test_standard_update_failure_raises_repository_error(
        self,
        repo: GenericRepository[_Entity, int],
        mock_provider: MagicMock,
    ) -> None:
        """Standard update failure (success=False) must raise RepositoryError."""
        update_result = _make_update_result(success=False, affected_rows=0)
        update_result.error_message = "DB error"
        mock_provider.execute_update.return_value = update_result
        entity = _Entity(id=1, name="Alice", version=0)

        with pytest.raises(RepositoryError):
            await repo.update(entity, check_version=False)

    @pytest.mark.asyncio
    async def test_missing_primary_key_raises_repository_error(
        self,
        repo: GenericRepository[_Entity, int],
        mock_provider: MagicMock,
    ) -> None:
        """Entity without primary key must raise RepositoryError."""
        entity = _Entity(id=None, name="Ghost", version=0)  # type: ignore[arg-type]

        with pytest.raises(RepositoryError, match="primary key"):
            await repo.update(entity, check_version=True)

    # --- Default behavior (check_version=None) ---

    @pytest.mark.asyncio
    async def test_versioned_entity_uses_optimistic_lock_by_default(
        self,
        repo: GenericRepository[_Entity, int],
        mock_provider: MagicMock,
    ) -> None:
        """Versioned entity should automatically use optimistic locking by default."""
        mock_provider.execute_update.return_value = _make_update_result(
            success=True, affected_rows=1
        )
        entity = _Entity(id=1, name="Alice", version=2)

        await repo.update(entity)

        where_clause: str = mock_provider.execute_update.call_args.args[2]
        assert "version" in where_clause.lower()
        assert entity.version == 3

    @pytest.mark.asyncio
    async def test_versioned_entity_can_explicitly_opt_out_of_locking(
        self,
        repo: GenericRepository[_Entity, int],
        mock_provider: MagicMock,
    ) -> None:
        """Versioned entity can explicitly opt out of optimistic locking."""
        mock_provider.execute_update.return_value = _make_update_result(
            success=True, affected_rows=1
        )
        entity = _Entity(id=1, name="Alice", version=2)

        await repo.update(entity, check_version=False)

        where_clause: str = mock_provider.execute_update.call_args.args[2]
        assert "version" not in where_clause.lower()
        assert entity.version == 2
