"""Session provider — registers ``SessionManagerImpl`` in the DI container."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.auth.session.manager import SessionManagerImpl
from quadkit.auth.storage.in_memory_stores import InMemorySessionStore
from quadkit.contracts.auth.protocols import AuthSessionManagerProtocol
from quadkit.contracts.core import HealthCheckResult, HealthStatus, ProviderPriority
from quadkit.di.provider import Provider
from quadkit.logging import get_logger

if TYPE_CHECKING:
    from quadkit.auth.storage.session_store import SessionStore
    from quadkit.contracts.core.di import (
        ContainerRegistrarProtocol,
        ContainerResolverProtocol,
    )

logger = get_logger(__name__)


class SessionProvider(Provider):
    """Registers :class:`~quadkit.auth.session.manager.SessionManagerImpl` in the container.

    Reads ``max_sessions_per_user`` from the supplied ``AuthConfig`` so that
    the concurrency limit is driven by application configuration.  When no
    config is given the session manager defaults to unlimited sessions.
    """

    def __init__(self, config: Any = None, **kwargs: Any) -> None:
        """Initialise the session provider.

        Args:
            config: Optional :class:`~quadkit.auth.config.AuthConfig`.  Used
                to read ``max_sessions_per_user`` and select the session store
                backend.  When ``None``, sane defaults are used.
            **kwargs: Ignored extra keyword arguments (forwarded from bundle).
        """
        super().__init__(name="sessions", priority=ProviderPriority.SECURITY)
        self._config = config

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        """Register :class:`SessionManagerImpl` as a singleton.

        The manager is built through a factory so an application can bind
        its own :class:`~quadkit.auth.storage.session_store.SessionStore`
        — a SQL or Redis backend — and have it picked up here. The store is
        resolved at first use rather than at registration time, because a
        host application's providers may register after this one; the same
        deferral :class:`~quadkit.auth.di.sub_providers.mfa_provider.MFAProvider`
        uses for ``UserStoreProtocol``.

        Without a bound store the manager falls back to
        :class:`~quadkit.auth.storage.in_memory_stores.InMemorySessionStore`,
        which does not survive a restart and cannot be shared between
        workers — right for development, wrong for a deployment.

        Args:
            container: The DI container registrar.
        """
        max_sessions: int | None = None

        if self._config is not None:
            max_sessions = getattr(self._config, "max_sessions_per_user", None)

        # One manager behind both bindings: two factories would build two
        # managers, and a session created through one would be invisible
        # to the other.
        built: dict[str, SessionManagerImpl] = {}

        async def build_session_manager(resolver: Any) -> SessionManagerImpl:
            from quadkit.auth.storage.session_store import SessionStore as _SessionStore

            if "manager" in built:
                return built["manager"]
            session_store: SessionStore | None = None
            resolve_optional = getattr(resolver, "resolve_optional", None)
            if callable(resolve_optional):
                session_store = await resolve_optional(_SessionStore)
            manager = SessionManagerImpl(
                session_store=session_store or InMemorySessionStore(),
                max_sessions_per_user=max_sessions,
            )
            built["manager"] = manager
            return manager

        container.singleton(SessionManagerImpl, factory=build_session_manager)
        container.singleton(AuthSessionManagerProtocol, factory=build_session_manager)
        logger.debug(
            "session_provider.registered",
            max_sessions_per_user=max_sessions
            if max_sessions is not None
            else "unlimited",
        )

    async def boot(self, container: ContainerResolverProtocol) -> None:
        """Boot the session provider.

        Args:
            container: The read-only container resolver.
        """
        logger.info("session_provider.started")

    async def shutdown(self) -> None:
        """Shut down the session provider."""
        logger.info("session_provider.shutdown")

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Return the health of the session subsystem.

        Args:
            timeout: Ignored; present for protocol compatibility.

        Returns:
            A healthy :class:`~quadkit.contracts.core.HealthCheckResult`.
        """
        return HealthCheckResult(
            component=self.name,
            status=HealthStatus.HEALTHY,
            details={
                "max_sessions_per_user": getattr(
                    self._config, "max_sessions_per_user", None
                )
            },
        )


__all__ = ["SessionProvider"]
