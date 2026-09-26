"""Query stats widget handler."""

from __future__ import annotations

from quadkit.contracts.admin import Stat, StatContent, Tone, WidgetParams
from quadkit.contracts.admin.errors import AdminError
from quadkit.contracts.data import DatabaseProviderProtocol
from quadkit.result import Ok, Result


class QueryStatsWidgetHandler:
    """Fetches aggregate query statistics.

    Args:
        db: injected DatabaseProviderProtocol.
    """

    def __init__(self, db: DatabaseProviderProtocol) -> None:
        """Initialize the handler.

        Args:
            db: Database provider protocol.
        """
        self._db = db

    async def get_data(self, params: WidgetParams) -> Result[StatContent, AdminError]:
        """Fetch query stats.

        Reports the pool's connection acquisition counters, degrading to an
        ``Unavailable`` stat when no pool is reachable.

        Args:
            params: Widget parameters.

        Returns:
            Result with StatContent or AdminError.
        """
        try:
            pool = await self._db.get_primary_pool()
            stats = await pool.get_pool_stats()
        except Exception:  # noqa: BLE001
            return Ok(
                StatContent(
                    stats=(
                        Stat(
                            label="In Progress",
                            value="Unavailable",
                            tone=Tone.WARNING,
                        ),
                    )
                )
            )
        acquired = int(stats.get("acquired_connections", 0))
        released = int(stats.get("released_connections", 0))
        in_progress = max(acquired - released, 0)
        return Ok(
            StatContent(
                stats=(
                    Stat(label="Acquired", value=str(acquired)),
                    Stat(label="Released", value=str(released)),
                    Stat(
                        label="In Progress",
                        value=str(in_progress),
                        tone=Tone.WARNING if in_progress else Tone.DEFAULT,
                    ),
                )
            )
        )


__all__ = ["QueryStatsWidgetHandler"]
