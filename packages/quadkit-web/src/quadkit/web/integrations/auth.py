"""Authentication integration for WebProvider."""

from __future__ import annotations

import inspect
from typing import Any, cast

from starlette.applications import Starlette

from quadkit.di.container import Container
from quadkit.logging import get_logger

logger = get_logger(__name__)


class AuthIntegration:
    """Handles authentication middleware configuration."""

    @staticmethod
    def _is_invocable_authenticator(candidate: Any) -> bool:
        """Check the candidate can be called as ``authenticate(request)``.

        Args:
            candidate: Resolved service candidate.

        Returns:
            True if the candidate is safe to invoke with a single request argument.
        """
        authenticate = getattr(candidate, "authenticate", None)
        if not callable(authenticate):
            return False
        try:
            signature = inspect.signature(authenticate)
        except (TypeError, ValueError):
            return True
        positional: list[inspect.Parameter] = [
            p
            for p in signature.parameters.values()
            if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
        ]
        if positional and positional[0].name in ("self", "cls"):
            positional = positional[1:]
        required = [p for p in positional if p.default is p.empty]
        return len(required) <= 1

    @staticmethod
    async def configure(app: Starlette, container: Container, web_config: Any) -> None:
        """Configure authentication middleware."""
        from quadkit.contracts.auth import IdentityResolverProtocol
        from quadkit.contracts.auth.guard import AuthenticatorProtocol
        from quadkit.contracts.exceptions import ContainerError
        from quadkit.web.middleware.auth import AuthenticationMiddleware

        identity_resolver = await container.resolve_optional(
            cast("Any", IdentityResolverProtocol)
        )

        authenticators = []
        try:
            candidates = await container.resolve_all(cast("Any", AuthenticatorProtocol))
            for candidate in candidates:
                if AuthIntegration._is_invocable_authenticator(candidate):
                    authenticators.append(candidate)
                else:
                    logger.warning(
                        "skipped_incompatible_authenticator",
                        authenticator=type(candidate).__name__,
                    )
            logger.info("resolved_authenticators", count=len(authenticators))
        except (LookupError, RuntimeError, ContainerError) as e:
            logger.warning("failed_to_resolve_authenticators", error=str(e))

        app.add_middleware(
            AuthenticationMiddleware,
            authenticators=authenticators,
            exclude_paths=web_config.auth_exclude_paths,
            enable_identity_resolution=web_config.enable_identity_resolution,
            identity_resolver=identity_resolver,
        )
        logger.info("Authentication middleware configured")

        await AuthIntegration._add_role_guard(app, container, web_config)

    @staticmethod
    async def _add_role_guard(
        app: Starlette, container: Container, web_config: Any
    ) -> None:
        """Register the role guard middleware after authentication.

        Roles are resolved per request from the container-bound
        :class:`~quadkit.web.middleware.role_guard.RoleResolverProtocol`,
        never from JWT claims. When rules are declared but no resolver is
        bound, startup fails fast — enforcement must never be silently off.

        Args:
            app: The Starlette application to configure.
            container: The DI container.
            web_config: The WebConfig driving the rules.
        """
        from starlette.middleware import Middleware

        from quadkit.contracts.exceptions import ContainerError
        from quadkit.contracts.exceptions.config import ConfigurationError
        from quadkit.web.middleware.role_guard import (
            RoleGuardMiddleware,
            RoleGuardRule,
            RoleResolverProtocol,
        )

        role_guard = getattr(web_config, "role_guard", None)
        rules = role_guard.rules if role_guard is not None else []
        if not rules:
            return

        resolver = None
        try:
            resolver = await container.resolve(cast("Any", RoleResolverProtocol))
        except (LookupError, RuntimeError, ContainerError) as e:
            logger.warning("failed_to_resolve_role_resolver", error=str(e))

        if resolver is None:
            raise ConfigurationError(
                "web.role_guard.rules declared but no RoleResolverProtocol is "
                "bound in the container. Bind one to enable role enforcement."
            )

        app.user_middleware.append(
            Middleware(
                RoleGuardMiddleware,
                rules=[
                    RoleGuardRule(path=rule.path, roles=list(rule.roles))
                    for rule in rules
                ],
                resolver=resolver,
            )
        )
        logger.info("Role guard middleware configured", rules=len(rules))
