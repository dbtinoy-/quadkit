"""GraphQL playground page protocol."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class GraphQLPlaygroundProtocol(Protocol):
    """Contract for the GraphQL playground page service.

    The web layer mounts the playground route against this contract only;
    the ``the optional provider`` package registers the concrete service. This
    keeps the web package free of any direct dependency on the graphql
    extension (extension independence — see ``.importlinter``).

    Implementations must be resolvable from the DI container under this
    protocol token; the web layer treats absence of the binding as
    "graphql not installed" and skips the playground silently.
    """

    @property
    def enabled(self) -> bool:
        """Whether the playground page should be served at all."""
        ...

    @property
    def page_path(self) -> str:
        """Route path at which the playground page is served."""
        ...

    @property
    def endpoint_path(self) -> str:
        """GraphQL endpoint path the page submits queries to."""
        ...

    @property
    def title(self) -> str:
        """Browser title for the playground page."""
        ...

    def render(self, endpoint: str) -> str:
        """Render the playground HTML document.

        Args:
            endpoint: Full URL path (already prefixed with any ASGI
                ``root_path``) of the GraphQL HTTP endpoint the page
                targets.

        Returns:
            The self-contained HTML document.
        """
        ...


__all__ = ["GraphQLPlaygroundProtocol"]
