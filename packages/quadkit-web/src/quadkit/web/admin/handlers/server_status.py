"""Server status widget handler for web admin dashboard."""

from __future__ import annotations

import platform
import threading
import time

from quadkit.contracts.admin import Stat, StatContent, Tone, WidgetParams
from quadkit.contracts.admin.errors import AdminError
from quadkit.result import Ok, Result

_PROCESS_START = time.monotonic()


class ServerStatusWidgetHandler:
    """Handler for the server_status widget.

    Reports real process information: Python version, process uptime, and
    thread count.
    """

    async def get_data(self, params: WidgetParams) -> Result[StatContent, AdminError]:
        """Fetch server status data.

        Args:
            params: Widget request parameters (unused for this widget).

        Returns:
            Result containing StatContent with process information.
        """
        return Ok(
            StatContent(
                stats=(
                    Stat(label="Python", value=platform.python_version()),
                    Stat(
                        label="Process Uptime (s)",
                        value=f"{int(self._uptime_seconds()):,}",
                    ),
                    Stat(
                        label="Threads",
                        value=str(threading.active_count()),
                        tone=Tone.INFO,
                    ),
                )
            )
        )

    @staticmethod
    def _uptime_seconds() -> float:
        return time.monotonic() - _PROCESS_START


__all__ = ["ServerStatusWidgetHandler"]
