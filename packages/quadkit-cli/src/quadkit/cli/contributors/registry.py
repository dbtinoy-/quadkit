from __future__ import annotations

from quadkit.contracts.cli.protocols import CliContributorProtocol


class CliContributorRegistry:
    """Registry for CLI contributors that populate the gen command surface.

    Each instance maintains its own isolated contributor map. Populated
    during DI boot via CliContributorSubProvider.
    """

    def __init__(self) -> None:
        self._contributors: dict[str, CliContributorProtocol] = {}

    def register(self, contributor: CliContributorProtocol) -> None:
        """Register a CLI contributor.

        Args:
            contributor: The contributor to register.
        """
        self._contributors[contributor.contributor_id] = contributor

    def get(self, contributor_id: str) -> CliContributorProtocol | None:
        """Look up a contributor by ID.

        Args:
            contributor_id: The contributor identifier.

        Returns:
            The contributor if found, else None.
        """
        return self._contributors.get(contributor_id)

    def get_all(self) -> list[CliContributorProtocol]:
        """Return all registered contributors in insertion order.

        Returns:
            A list of all registered CliContributorProtocol instances.
        """
        return list(self._contributors.values())
