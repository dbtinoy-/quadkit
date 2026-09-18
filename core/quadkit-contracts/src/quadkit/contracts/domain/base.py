"""Basic domain modelling protocols and types.

This module defines ``DomainModelProtocol`` which specifies the interface
for domain models in the Quadkit framework. The actual implementation
lives in ``quadkit.domain.base``.
"""

from __future__ import annotations

from typing import Any, ClassVar, Protocol, TypeVar, runtime_checkable


@runtime_checkable
class DomainModelProtocol(Protocol):
    """Protocol defining the interface for domain models.

    This protocol is intentionally **Pydantic-aligned**: it mirrors the
    Pydantic v2 ``BaseModel`` API surface because ``DomainModel`` (the
    concrete base in ``quadkit.domain``) builds on Pydantic v2.  This
    is a deliberate design decision — all first-party implementations are
    Pydantic models, so tight alignment removes friction.

    The trade-off is that non-Pydantic implementations must provide
    compatible shims for ``model_dump``, ``model_validate``, etc.

    ``model_rebuild`` and ``model_extra`` are **excluded** from this
    protocol: they are Pydantic implementation internals not relevant to
    the domain-model contract.
    """

    model_config: ClassVar[dict[str, Any]] = {}

    def model_dump(
        self,
        *,
        mode: str = "python",
        exclude: set[str] | None = None,
        include: set[str] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Return a dict representation of the model.

        Args:
            mode: "python" or "json" - json converts to serializable types
            exclude: Fields to exclude from output
            include: Fields to include in output (if None, includes all)
        """
        ...

    def model_dump_json(self, **kwargs: Any) -> str:
        """Return a JSON string representation of the model."""
        ...

    @classmethod
    def model_validate(cls, data: dict[str, Any], **kwargs: Any) -> Any:
        """Create an instance from a dictionary."""
        ...

    @classmethod
    def model_validate_json(cls, json_str: str, **kwargs: Any) -> Any:
        """Create an instance from a JSON string."""
        ...

    def model_copy(
        self,
        *,
        update: dict[str, Any] | None = None,
        deep: bool = False,
    ) -> Any:
        """Create a copy of the model with optional updates.

        Args:
            update: Fields to update in the copy
            deep: If True, perform a deep copy
        """
        ...

    def model_json_schema(self) -> dict[str, Any]:
        """Generate JSON schema for the model."""
        ...

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the model with the given arguments."""
        ...


ID = TypeVar("ID")


__all__ = ["ID", "DomainModelProtocol"]
