"""Web contributor for quadkit-auth — exposes the login/register controllers.

Before this contributor existed, ``quadkit-auth`` shipped middleware that
exempted ``/auth/login`` and ``/auth/register`` and a rate limiter that named
the same paths, but no package implemented either route. An application that
imported ``AuthModule`` therefore authenticated nothing and refused
everything: every guarded controller answered ``401 Authentication required``
and no credential could ever satisfy it, because the endpoint that mints
credentials did not exist.

The contributor protocol is the framework's hook for exactly this: a package
declares its HTTP surface once, and the web provider merges it into the route
table without the consuming application naming it. That is the framework
correct split — the playground does not need to generate a login controller,
and a hand-written application gets the routes for free.
"""

from __future__ import annotations

from typing import Any


class AuthWebContributor:
    """Registers the authentication controllers with the web provider.

    Registered via entry-point in ``pyproject.toml``::

        [project.entry-points."quadkit.web.contributors"]
        auth = "quadkit.auth.web.contributor:AuthWebContributor"

    Implements :class:`~quadkit.contracts.web.ConditionalWebContributorProtocol`:
    the routes are contributed only when the application actually configured
    ``AuthModule``. Being *installed* is not being *wired* — a project that
    depends on this distribution without configuring the module has no
    ``AuthenticationService`` to inject, and registering the controller anyway
    fails container validation for every route in the app, not just this one.
    """

    @property
    def contributor_id(self) -> str:
        """Return the unique contributor identifier.

        Returns:
            The string ``"auth"``.
        """
        return "auth"

    def applies_to(self, container: Any) -> bool:
        """Whether the application wired the auth module.

        ``AuthenticationService`` is what ``AuthController`` injects, and it
        exists in the container exactly when ``AuthModule`` was configured, so
        its presence is the whole condition. Queried while the web provider
        registers — after the infrastructure modules and before the web
        surface, which is the order the composition root assembles them in.

        Args:
            container: The DI container being built.

        Returns:
            True when the auth service layer is registered, else False.
        """
        from quadkit.auth.authn.services import AuthenticationService

        try:
            return bool(container.has(AuthenticationService))
        except Exception:  # noqa: BLE001 — a container that cannot answer is a container without auth
            return False

    def get_controllers(self) -> list[type[Any]]:
        """Return the controllers this package serves.

        The import is deferred so that importing the contributor — which the
        web provider does at boot for every installed package — does not drag
        in the whole auth stack unless the routes are actually wanted.

        Returns:
            A list containing :class:`AuthController`.
        """
        from quadkit.auth.web.controllers import AuthController

        return [AuthController]

    def get_middleware(self) -> list[type[Any]]:
        """Return middleware classes contributed by the auth package.

        The auth middleware is contributed by ``AuthModule`` through the DI
        graph rather than through this hook, so there is nothing to add here.

        Returns:
            An empty list.
        """
        return []

    async def mount_to_app(self, app: Any, container: object) -> None:
        """No-op mount hook.

        Auth exposes routes via controllers rather than by mounting a
        sub-application.

        Args:
            app: The ASGI application (unused).
            container: The DI container (unused).
        """


__all__ = ["AuthWebContributor"]
