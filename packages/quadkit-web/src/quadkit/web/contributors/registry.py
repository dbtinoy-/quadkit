"""Web contributor registry.

Registry for tracking discovered web contributors that provide controllers
and middleware to the web provider.
"""

from __future__ import annotations

from quadkit.contracts.web import WebContributorProtocol


class WebContributorRegistry:
    """Registry for web contributors discovered via entry-points.

    The web provider discovers contributors during registration phase
    and stores them in this registry for tracking and debugging purposes.
    """

    def __init__(self) -> None:
        """Initialize an empty registry."""
        self._contributors: dict[str, WebContributorProtocol] = {}

    def register(self, contributor: WebContributorProtocol) -> None:
        """Register a web contributor.

        Args:
            contributor: The contributor instance to register.
        """
        self._contributors[contributor.contributor_id] = contributor

    def get(self, contributor_id: str) -> WebContributorProtocol | None:
        """Get a contributor by ID.

        Args:
            contributor_id: The unique contributor identifier.

        Returns:
            The contributor instance or None if not found.
        """
        return self._contributors.get(contributor_id)

    def get_all(self) -> list[WebContributorProtocol]:
        """Get all registered contributors.

        Returns:
            List of all registered contributors in registration order.
        """
        return list(self._contributors.values())


__all__ = ["WebContributorRegistry"]
