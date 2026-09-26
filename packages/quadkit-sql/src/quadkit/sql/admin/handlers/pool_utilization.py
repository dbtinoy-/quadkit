"""Pool utilization widget handler."""

from __future__ import annotations

from quadkit.contracts.admin import Stat, StatContent, Tone, WidgetParams
from quadkit.contracts.admin.errors import AdminError
from quadkit.contracts.data import DatabaseProviderProtocol
from quadkit.result import Ok, Result


class PoolUtilizationWidgetHandler:
    """Fetches database pool utilization data.

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
        """Fetch pool stats.

        Reads live statistics from the provider's primary connection pool,
        degrading to an ``Unavailable`` stat when no pool is reachable.

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
                            label="Active Connections",
                            value="Unavailable",
                            tone=Tone.WARNING,
                        ),
                    )
                )
            )
        active = int(stats.get("active_connections", 0))
        total = int(stats.get("max_connections", 0))
        utilization = round(float(stats.get("utilization_rate", 0.0)) * 100, 1)
        return Ok(
            StatContent(
                stats=(
                    Stat(
                        label="Active Connections",
                        value=f"{active}/{total}",
                        tone=Tone.SUCCESS if utilization < 80 else Tone.WARNING,
                    ),
                    Stat(
                        label="Utilization",
                        value=f"{utilization}%",
                        tone=Tone.SUCCESS if utilization < 80 else Tone.DANGER,
                    ),
                )
            )
        )


__all__ = ["PoolUtilizationWidgetHandler"]
