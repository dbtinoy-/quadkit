from __future__ import annotations

from typing import Any

from quadkit.contracts.admin import PageContent
from quadkit.contracts.admin.widget_content import EmptyContent, Stat, StatContent
from quadkit.contracts.infra.cache.protocols import CacheBackendProtocol
from quadkit.logging import get_logger

logger = get_logger(__name__)


class CacheOverviewPage:
    """Dashboard overview for /admin/cache."""

    def __init__(self, cache: CacheBackendProtocol | None = None) -> None:
        self._cache = cache

    async def handle(self, request: Any) -> PageContent:
        if self._cache is None:
            return PageContent(
                title="Cache",
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
        errors = metrics.get("errors", "N/A")

        return PageContent(
            title="Cache",
            body=StatContent(
                stats=(
                    Stat(
                        label="Backend Status",
                        value="OK" if healthy else "Down",
                        delta=f"{latency}ms" if healthy else None,
                        icon="activity",
                    ),
                    Stat(
                        label="Operations",
                        value=str(total_ops),
                        icon="database",
                    ),
                    Stat(
                        label="Hit Ratio",
                        value=str(hit_rate),
                        icon="trending-up",
                    ),
                    Stat(
                        label="Errors",
                        value=str(errors),
                        icon="x-circle",
                    ),
                )
            ),
        )
