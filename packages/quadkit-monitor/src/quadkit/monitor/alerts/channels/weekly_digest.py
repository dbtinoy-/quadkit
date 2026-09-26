"""Weekly digest alert channel — accumulates, flushes on schedule."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from quadkit.logging import get_logger
from quadkit.serialization import dumps, loads

if TYPE_CHECKING:
    from quadkit.contracts.infra.cache.protocols import CacheBackendProtocol
    from quadkit.contracts.observability.metrics import AlertDispatcherProtocol

logger = get_logger(__name__)

__all__ = ["WeeklyDigestDispatcher"]


class WeeklyDigestDispatcher:
    """Accumulates alerts in a buffer and flushes as a single digest.

    Args:
        buffer_store: :class:`~quadkit.contracts.infra.cache.CacheBackendProtocol`
            used to persist buffered alerts across process restarts.
        flush_dispatcher: The dispatcher that receives the compiled digest
            (typically a Slack channel or logging dispatcher).
        digest_key: Cache key for the buffer. Defaults to
            ``"monitor:weekly_digest"``.
    """

    def __init__(
        self,
        buffer_store: CacheBackendProtocol,
        flush_dispatcher: AlertDispatcherProtocol,
        digest_key: str = "monitor:weekly_digest",
    ) -> None:
        self._buffer_store = buffer_store
        self._flush_dispatcher = flush_dispatcher
        self._digest_key = digest_key
        # Serialises the read-modify-write in _append so concurrent alerts
        # in this process cannot lose each other's entries.
        self._append_lock = asyncio.Lock()

    async def send_alert(
        self,
        title: str,
        message: str,
        severity: str,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Buffer an alert for the next digest flush."""
        await self._append({"title": title, "message": message, "severity": severity})

    async def send_metric_alert(
        self,
        metric_name: str,
        current_value: float,
        threshold: float,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Buffer a metric alert for the next digest flush."""
        await self._append(
            {
                "title": f"Metric: {metric_name}",
                "message": f"{metric_name} = {current_value} (threshold: {threshold})",
                "severity": (context or {}).get("severity", "high"),
            }
        )

    async def _append(self, entry: dict[str, Any]) -> None:
        async with self._append_lock:
            raw_result = await self._buffer_store.get(self._digest_key)
            raw = raw_result.unwrap_or(None)
            entries: list[dict[str, Any]] = loads(raw) if raw else []
            entries.append(entry)
            await self._buffer_store.set(
                self._digest_key,
                dumps(entries).decode()
                if isinstance(dumps(entries), bytes)
                else dumps(entries),
            )

    async def flush(self) -> None:
        """Send the accumulated digest and clear the buffer."""
        raw_result = await self._buffer_store.get(self._digest_key)
        raw = raw_result.unwrap_or(None)
        if not raw:
            return
        entries: list[dict[str, Any]] = loads(raw)
        if not entries:
            return

        # Delete buffer BEFORE processing to avoid losing items added during flush
        await self._buffer_store.delete(self._digest_key)

        lines = [f"**Weekly Digest — {len(entries)} alerts**"]
        for e in entries:
            lines.append(
                f"[{e.get('severity', 'info').upper()}] {e.get('title', '')}: {e.get('message', '')}"
            )
        digest_text = "\n".join(lines)

        await self._flush_dispatcher.send_alert(
            title="Weekly Digest",
            message=digest_text,
            severity="low",
        )
        logger.info("weekly_digest_flushed", alert_count=len(entries))
