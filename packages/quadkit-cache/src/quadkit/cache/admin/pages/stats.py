from __future__ import annotations

from typing import Any

from quadkit.contracts.admin import PageContent
from quadkit.contracts.admin.widget_content import EmptyContent, Stat, StatContent
from quadkit.contracts.infra.cache.protocols import CacheBackendProtocol
from quadkit.logging import get_logger

logger = get_logger(__name__)


class CacheStatsPage:
    """Detailed cache statistics for /admin/cache/stats."""

    def __init__(self, cache: CacheBackendProtocol | None = None) -> None:
        self._cache = cache

    async def handle(self, request: Any) -> PageContent:
        if self._cache is None:
            return PageContent(
                title="Cache Statistics",
                body=EmptyContent(
                    title="Cache Unavailable",
                    message="The cache backend could not be resolved.",
                    icon="database",
                ),
            )
        try:
            health = await self._cache.health_check()
            healthy = health.is_healthy()
            latency = int(health.duration_ms)
            details = health.details or {}
            metrics = details.get("metrics", {}) if isinstance(details, dict) else {}
        except Exception:
            healthy = False
            latency = 0
            metrics = {}

        hit_rate = metrics.get("hit_rate", "N/A")
        if isinstance(hit_rate, (int, float)):
            hit_rate = f"{hit_rate * 100:.0f}%"
        total_ops = metrics.get("total_operations", "N/A")
        avg_latency = metrics.get("avg_latency_ms", 0)
        if isinstance(avg_latency, (int, float)):
            avg_latency = f"{avg_latency:.1f}ms"

        return PageContent(
            title="Cache Statistics",
            body=StatContent(
                stats=(
                    Stat(
                        label="Backend",
                        value="OK" if healthy else "Down",
                        delta=f"{latency}ms" if healthy else None,
                        icon="activity",
                    ),
                    Stat(
                        label="Hit Ratio",
                        value=str(hit_rate),
                        icon="trending-up",
                    ),
                    Stat(
                        label="Operations",
                        value=str(total_ops),
                        icon="database",
                    ),
                    Stat(
                        label="Avg Latency",
                        value=str(avg_latency),
                        icon="clock",
                    ),
                )
            ),
        )
