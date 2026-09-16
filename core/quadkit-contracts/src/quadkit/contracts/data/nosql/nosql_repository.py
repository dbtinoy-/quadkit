"""NoSQL repository protocols for document-oriented data access.

Provides a generic ``DocumentRepositoryProtocol[T]`` that mirrors
:class:`~quadkit.contracts.data.repository.RepositoryProtocol`
but uses document semantics (filter dicts, no SQL assumptions).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, TypeVar, runtime_checkable

if TYPE_CHECKING:
    import builtins

    from quadkit.contracts.domain.specification import SpecificationProtocol

T = TypeVar("T")


@runtime_checkable
class DocumentRepositoryProtocol(Protocol[T]):
    """Repository protocol for document-oriented storage.

    Mirrors ``RepositoryProtocol`` but uses document semantics:

    - No SQL ``table_name`` / ``key_field`` assumptions
    - Filter expressions instead of WHERE clauses
    - Aggregation pipeline support
    """

    async def get(self, document_id: str) -> T | None:
        """Retrieve a document by its ID."""
        ...

    async def list(
        self,
        skip: int = 0,
        limit: int = 100,
        *,
        sort: list[tuple[str, int]] | None = None,
        **filters: Any,
    ) -> list[T]:
        """List documents with pagination and optional filters."""
        ...

    async def find_by_filter(self, filter: dict[str, Any]) -> builtins.list[T]:
        """Find documents matching a raw filter expression."""
        ...

    async def find_by_spec(self, spec: SpecificationProtocol[T]) -> builtins.list[T]:
        """Find documents matching a specification."""
        ...

    async def count(self, **filters: Any) -> int:
        """Count documents matching filters."""
        ...

    async def save(self, entity: T) -> T:
        """Insert or update a document (upsert semantics)."""
        ...

    async def delete(self, document_id: str) -> bool:
        """Delete a document by ID."""
        ...

    async def save_many(self, entities: builtins.list[T]) -> builtins.list[T]:
        """Bulk insert / update documents."""
        ...

    async def delete_many(self, document_ids: builtins.list[str]) -> int:
        """Bulk delete documents by IDs."""
        ...


__all__ = ["DocumentRepositoryProtocol", "T"]
