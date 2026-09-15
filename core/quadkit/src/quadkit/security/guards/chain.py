"""Immutable guard chain for authorization pipelines.

Provides :class:`GuardChainImpl`, an immutable, composable chain of guards that
collectively determine whether a request may proceed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.contracts.exceptions.middleware import MiddlewareGuardError
from quadkit.logging import get_logger

if TYPE_CHECKING:
    from quadkit.contracts.web import GuardProtocol

logger = get_logger(__name__)


class GuardChainImpl:
    """Immutable chain of authorization guards.

    Guards determine whether a request should proceed based on the
    provided context. The chain is immutable — each :meth:`add` call
    returns a new chain leaving the original unchanged.

    Example::

        from quadkit.security.guards import GuardChainImpl

        chain = (
            GuardChainImpl()
            .add(AuthenticationGuard())
            .add(RoleGuard("admin"))
            .add(PermissionGuard("users:write"))
        )

        allowed = await chain.check(context)
    """

    __slots__ = ("_guards", "_propagate_exceptions")

    def __init__(
        self,
        guards: list[GuardProtocol] | None = None,
        *,
        propagate_exceptions: bool = False,
    ) -> None:
        """Initialize the guard chain.

        Args:
            guards: Optional list of guards.
            propagate_exceptions: When ``True``, exceptions raised by a guard
                are re-raised instead of being silently converted to ``False``.
                Use this when callers need to distinguish a guard crash from an
                explicit deny.  Defaults to ``False`` (original behaviour).
        """
        self._guards: list[GuardProtocol] = list(guards) if guards else []
        self._propagate_exceptions: bool = propagate_exceptions

    def add(self, guard: GuardProtocol) -> GuardChainImpl:
        """Return a new chain with the guard appended.

        The new chain inherits the ``propagate_exceptions`` flag of the
        current chain so that builder-style usage preserves the setting.

        Args:
            guard: A guard implementing the GuardProtocol protocol.

        Returns:
            A new ``GuardChainImpl`` instance with the guard added.
        """
        return GuardChainImpl(
            [*self._guards, guard],
            propagate_exceptions=self._propagate_exceptions,
        )

    async def execute(self, context: dict[str, Any]) -> bool:
        """Execute all guards against the given context.

        Alias for :meth:`check`.

        Args:
            context: Arbitrary context dict with request information.

        Returns:
            True if all guards allow the request, False otherwise.
        """
        return await self.check(context)

    async def check(self, context: dict[str, Any]) -> bool:
        """Check if all guards allow the request to proceed.

        Args:
            context: Arbitrary context dict with request information.

        Returns:
            True if all guards allow the request, False otherwise.
        """
        for guard in self._guards:
            try:
                if not await guard.can_activate(context):  # type: ignore[arg-type]
                    logger.warning(
                        "guard_denied",
                        guard_type=type(guard).__name__,
                        subject=context.get("subject") or context.get("user_id"),
                        resource=context.get("resource") or context.get("path"),
                    )
                    return False
            except (RuntimeError, ValueError, TypeError, OSError, AttributeError) as e:
                logger.error(
                    "guard_error",
                    guard_type=type(guard).__name__,
                    error=str(e),
                )
                if self._propagate_exceptions:
                    raise
                return False

        return True

    async def check_or_raise(
        self,
        context: dict[str, Any],
        message: str = "Access denied",
    ) -> None:
        """Check guards and raise MiddlewareGuardError if any deny access.

        Args:
            context: Arbitrary context dict with request information.
            message: Error message to use if access is denied.

        Raises:
            MiddlewareGuardError: If any guard denies access.
        """
        for guard in self._guards:
            try:
                if not await guard.can_activate(context):  # type: ignore[arg-type]
                    logger.warning(
                        "guard_rejected",
                        guard_type=type(guard).__name__,
                        subject=context.get("subject") or context.get("user_id"),
                        resource=context.get("resource") or context.get("path"),
                    )
                    raise MiddlewareGuardError(
                        message=message,
                        guard=type(guard).__name__,
                    )
            except MiddlewareGuardError:
                raise
            except Exception as e:  # noqa: BLE001 — guard error boundary: non-GuardErrors logged and surfaced
                logger.error(
                    "guard_exception",
                    guard_type=type(guard).__name__,
                    error=str(e),
                )
                raise MiddlewareGuardError(
                    message=f"GuardProtocol error: {e}",
                    guard=type(guard).__name__,
                ) from e

    def __len__(self) -> int:
        """Return the number of guards in the chain."""
        return len(self._guards)

    def __repr__(self) -> str:
        return f"GuardChainImpl({len(self._guards)} guards)"


__all__ = ["GuardChainImpl"]
