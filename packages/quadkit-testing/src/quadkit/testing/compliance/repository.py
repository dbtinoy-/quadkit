"""Contract compliance suite for ``RepositoryProtocol`` implementations.

Subclass :class:`RepositoryCompliance` and implement
:meth:`create_repository` and :meth:`create_entity`::

    from quadkit.testing.compliance import RepositoryCompliance

    class TestUserRepository(RepositoryCompliance):
        async def create_repository(self):
            return InMemoryUserRepository()

        def create_entity(self, **overrides):
            return User(id=str(uuid4()), name="Alice", **overrides)
"""

from __future__ import annotations

from abc import abstractmethod
from typing import Any, Generic, TypeVar

import pytest

__all__ = ["RepositoryCompliance"]

T = TypeVar("T")


class RepositoryCompliance(Generic[T]):
    """Reusable test suite for any ``RepositoryProtocol[T]`` implementation.

    Verifies that the repository satisfies the standard persistence
    contract: save, get, delete, list.

    Subclass and implement :meth:`create_repository` and
    :meth:`create_entity`:

    .. code-block:: python

        class TestInMemoryUserRepo(RepositoryCompliance[User]):
            async def create_repository(self):
                return InMemoryUserRepository()

            def create_entity(self, **overrides):
                return User(id=str(uuid4()), name="Alice")
    """

    @abstractmethod
    async def create_repository(self) -> Any:
        """Return a fresh, empty repository instance."""
        ...

    @abstractmethod
    def create_entity(self, **overrides: Any) -> T:
        """Return a new entity instance suitable for persistence."""
        ...

    # ------------------------------------------------------------------
    # Core contract tests
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_save_and_get(self) -> None:
        """save then get returns the entity."""
        repo = await self.create_repository()
        entity = self.create_entity()
        await repo.save(entity)
        found = await repo.get(entity.id)  # type: ignore[attr-defined]
        assert found is not None
        assert found.id == entity.id  # type: ignore[attr-defined]
