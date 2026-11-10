"""MCP logging handler — structured log forwarding from server to client.

Implements the MCP Logging specification so that server-side log events
can be forwarded to the MCP client via notifications.

https://spec.modelcontextprotocol.io/specification/server/utilities/logging/
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.logging import (
    get_logger,
)
from quadkit.result import Ok, Result

if TYPE_CHECKING:
    from quadkit.contracts.mcp.exceptions import MCPError

logger = get_logger(__name__)

# MCP-defined log levels (syslog-inspired, lower = more severe)
_MCP_LEVELS = frozenset(
    ["debug", "info", "notice", "warning", "error", "critical", "alert", "emergency"]
)


class LoggingHandler:
    """MCP logging capability — forward structured logs to the connected client.

    The MCP spec allows the server to emit ``notifications/message`` events
    that are delivered to the client as log entries.  This handler keeps a
    configurable minimum level and holds a reference to a *send callback* so
    it can push notifications asynchronously.

    Usage in provider wiring::

        logging_handler = LoggingHandler()
        server.register_logging_handler(logging_handler)

    The transport layer calls ``set_notify_callback`` once the client
    connection is established.

    Example client-directed log emission::

        await logging_handler.log("info", "Ingestion started", data={"docs": 5})
    """

    def __init__(self, *, min_level: str = "info") -> None:
        """Initialize the logging handler.

        Args:
            min_level: Minimum log level to forward to the client
                (one of the MCP syslog levels).  Default is ``"info"``.
        """
        if min_level not in _MCP_LEVELS:
            msg = f"Invalid MCP log level '{min_level}'. Must be one of {sorted(_MCP_LEVELS)}"
            raise ValueError(msg)
        self._min_level = min_level
        self._notify_callback: Any | None = None
        self._level_order = list(_MCP_LEVELS)  # preserved insertion order

    def set_notify_callback(self, callback: Any) -> None:
        """Register a coroutine callback for sending log notifications.

        The callback receives a single ``dict`` which is a full JSON-RPC
        ``notifications/message`` payload.

        Args:
            callback: Async callable ``callback(notification: dict) -> None``.
        """
        self._notify_callback = callback

    async def set_level(
        self, level: str = "info", **_kwargs: Any
    ) -> Result[dict[str, Any], MCPError]:
        """Handle ``logging/setLevel`` MCP method from the client.

        Args:
            level: New minimum level (MCP syslog name).
            **_kwargs: Ignored extra params for forward-compatibility.

        Returns:
            ``Ok({})`` (MCP spec requires an empty result payload).
        """
        if level not in _MCP_LEVELS:
            level = "info"
        self._min_level = level
        logger.info("mcp_log_level_changed", new_level=level)
        return Ok({})

    async def log(
        self,
        level: str,
        message: str,
        data: dict[str, Any] | None = None,
        logger_name: str | None = None,
    ) -> None:
        """Emit a structured log entry to the MCP client.

        If the *level* is below the current minimum, the entry is silently
        dropped.  Locally, only the event and severity are recorded; the
        client-supplied message and data are not written to server logs because
        they may contain sensitive prompts, credentials, or user content.

        Args:
            level: MCP syslog level name.
            message: Human-readable log message.
            data: Optional structured data payload.
            logger_name: Optional logger name shown to the client.
        """
        if not self._is_at_or_above_min(level):
            return

        # Client-controlled message/data can contain secrets or user content.
        local_log = getattr(logger, _map_level(level), logger.info)
        local_log("mcp_client_log", level=level)

        if self._notify_callback is None:
            return

        notification: dict[str, Any] = {
            "jsonrpc": "2.0",
            "method": "notifications/message",
            "params": {
                "level": level,
                "message": message,
            },
        }
        if data:
            notification["params"]["data"] = data
        if logger_name:
            notification["params"]["logger"] = logger_name

        try:
            await self._notify_callback(notification)
        except Exception as exc:  # noqa: BLE001 — log notification is best-effort
            logger.warning("mcp_log_notify_failed", error_type=type(exc).__name__)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _is_at_or_above_min(self, level: str) -> bool:
        """Return True if *level* is at or above the current minimum.

        Uses the ordered index of the MCP syslog levels list.
        """
        levels_ordered = [
            "debug",
            "info",
            "notice",
            "warning",
            "error",
            "critical",
            "alert",
            "emergency",
        ]
        try:
            min_idx = levels_ordered.index(self._min_level)
            lvl_idx = levels_ordered.index(level)
            return lvl_idx >= min_idx
        except ValueError:
            return False


def _map_level(mcp_level: str) -> str:
    """Map an MCP syslog level to a structlog method name."""
    mapping = {
        "debug": "debug",
        "info": "info",
        "notice": "info",
        "warning": "warning",
        "error": "error",
        "critical": "critical",
        "alert": "critical",
        "emergency": "critical",
    }
    return mapping.get(mcp_level, "info")


__all__ = ["LoggingHandler"]
