"""Web contributor discovery via entry-points.

Discovers and loads web contributors from installed packages via the
``quadkit.web.contributors`` entry-point group. Failed contributors
are logged but do not halt the discovery process.
"""

from __future__ import annotations

from importlib.metadata import entry_points

from quadkit.contracts.web import WebContributorProtocol
from quadkit.logging import get_logger

logger = get_logger(__name__)

ENTRY_POINT_GROUP = "quadkit.web.contributors"


def load_web_contributors() -> list[WebContributorProtocol]:
    """Load web contributors from entry-points.

    Scans the ``quadkit.web.contributors`` entry-point group and loads
    each registered contributor class. Failed loads (import errors,
    instantiation failures) are logged and skipped without halting
    the discovery process.

    Returns:
        List of successfully loaded and instantiated contributor instances.

    Example:
        A package registers a contributor via pyproject.toml::

            [project.entry-points."quadkit.web.contributors"]
            graphql = "the optional provider module:GraphQLWebContributor"

        The web provider loads all contributors at startup::

            contributors = load_web_contributors()
            for contributor in contributors:
                logger.info(f"Loaded contributor: {contributor.contributor_id}")
    """
    contributors: list[WebContributorProtocol] = []

    for contributor_entry_point in entry_points(group=ENTRY_POINT_GROUP):
        try:
            contributor_class = contributor_entry_point.load()
            contributor = contributor_class()
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "web.contributor_load_failed",
                name=getattr(contributor_entry_point, "name", "<unknown>"),
                error=str(exc),
            )
            continue

        contributors.append(contributor)

    return contributors


__all__ = ["ENTRY_POINT_GROUP", "load_web_contributors"]
