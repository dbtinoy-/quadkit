"""Feature flag protocols for the framework.

These protocols live in ``quadkit.contracts`` so that other packages may
rely on the abstract interface rather than importing concrete
implementations from ``quadkit.feature_flags`` or the enterprise extension.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from quadkit.contracts.feature_flags.models import FlagEvaluation, FlagValue


@runtime_checkable
class FlagProviderProtocol(Protocol):
    """Protocol for reading feature flags.

    * Supports synchronous and asynchronous access.  Implementations may be
      backed by in-memory maps, redis, remote services, etc.
    * Context parameter is provided for user/tenant/environment lookup.
    * Variant resolution is part of the contract, allowing A/B testing or
      percentage-based flags.
    * Write methods are deliberately excluded; see :class:`MutableFlagProviderProtocol`
      for providers that support updates.
    * Async methods are the primary entry points (no suffix).  Sync variants
      carry a ``_sync`` suffix.
    """

    async def get_flag(
        self,
        name: str,
        *,
        default: bool = False,
        context: dict[str, Any] | None = None,
    ) -> bool:  # pragma: no cover - protocol
        """Asynchronously evaluate the boolean value of a flag.

        This is the **primary** entry point for all applications.
        ``context`` may contain arbitrary data used by the provider to make a
        decision (e.g. user id, tenant id, request headers).
        """

    def get_flag_sync(
        self,
        name: str,
        *,
        default: bool = False,
        context: dict[str, Any] | None = None,
    ) -> bool:  # pragma: no cover - protocol
        """Synchronously evaluate the boolean value of a flag.

        Only suitable when the backing store is fully in-memory and no I/O is
        required.  Prefer :meth:`get_flag` in async contexts.
        """

    async def get_variant(
        self,
        name: str,
        *,
        default: str = "",
        context: dict[str, Any] | None = None,
    ) -> str:  # pragma: no cover - protocol
        """Asynchronously return a string variant for an A/B test or multivalue flag.

        This is the **primary** entry point.  Not all providers will support
        variants; those may simply return ``default``.
        """

    def get_variant_sync(
        self,
        name: str,
        *,
        default: str = "",
        context: dict[str, Any] | None = None,
    ) -> str:  # pragma: no cover - protocol
        """Synchronously return a string variant for an A/B test or multivalue flag.

        Only suitable when the backing store is fully in-memory.  Prefer
        :meth:`get_variant` in async contexts.
        """


@runtime_checkable
class MutableFlagProviderProtocol(FlagProviderProtocol, Protocol):
    """Optional extension of :class:`FlagProviderProtocol` that supports writes."""

    async def set_flag(
        self,
        name: str,
        value: bool,
    ) -> None:  # pragma: no cover - protocol
        """Asynchronously create or update a boolean flag value.

        This is the **primary** entry point.  Required for providers backed by
        remote stores (Redis, database, etc.).  Implementations with an
        in-memory backing store may perform the operation synchronously.
        """

    def set_flag_sync(
        self, name: str, value: bool
    ) -> None:  # pragma: no cover - protocol
        """Synchronously create or update a boolean flag value.

        Only suitable when the backing store is fully in-memory.  Prefer
        :meth:`set_flag` in async contexts.
        """

    async def set_variant(
        self,
        name: str,
        variant: str,
    ) -> None:  # pragma: no cover - protocol
        """Asynchronously create or update the active variant for a flag.

        This is the **primary** entry point.
        """

    def set_variant_sync(
        self,
        name: str,
        variant: str,
    ) -> None:  # pragma: no cover - protocol
        """Synchronously create or update the active variant for a flag.

        Only suitable when the backing store is fully in-memory.  Prefer
        :meth:`set_variant` in async contexts.
        """


@runtime_checkable
class FlagManagerProtocol(Protocol):
    """Manages the lifecycle of feature flag providers and evaluates flags.

    The manager chains multiple ``FlagProviderProtocol`` instances in order of priority.
    Evaluation short-circuits to the first provider that can resolve the flag.
    """

    def add_provider(self, provider: FlagProviderProtocol, priority: int = 50) -> None:
        """Register a flag provider at the given priority level.

        Higher priority values are queried first. Providers with equal
        priority are queried in registration order.

        Args:
            provider: The flag provider to register.
            priority: Resolution priority (higher = queried first).
        """
        ...

    async def is_enabled(
        self,
        key: str,
        context: dict[str, Any] | None = None,
    ) -> bool:
        """Evaluate a boolean feature flag.

        Args:
            key: The flag identifier.
            context: Optional evaluation context (user, tenant, etc.).

        Returns:
            True if the flag is enabled, False otherwise.

        Raises:
            FlagNotFoundError: If no provider can resolve the flag.
        """
        ...

    async def get_value(
        self,
        key: str,
        default: FlagValue,
        context: dict[str, Any] | None = None,
    ) -> FlagValue:
        """Evaluate a feature flag and return its resolved value.

        Args:
            key: The flag identifier.
            default: Fallback value when the flag cannot be resolved.
            context: Optional evaluation context.

        Returns:
            The resolved FlagValue, or ``default`` if not found.
        """
        ...

    async def evaluate(
        self,
        key: str,
        context: dict[str, Any] | None = None,
    ) -> FlagEvaluation:
        """Return the full evaluation result including metadata.

        Args:
            key: The flag identifier.
            context: Optional evaluation context.

        Returns:
            A FlagEvaluation with value, type, reason, and metadata.

        Raises:
            FlagNotFoundError: If no provider can resolve the flag.
        """
        ...

    async def get_all_flags(
        self,
        context: dict[str, Any] | None = None,
    ) -> dict[str, FlagEvaluation]:
        """Return evaluations for all known flags.

        Args:
            context: Optional evaluation context applied to every flag.

        Returns:
            Mapping of flag key to its FlagEvaluation.
        """
        ...


__all__ = [
    "FlagManagerProtocol",
    "FlagProviderProtocol",
    "MutableFlagProviderProtocol",
]
