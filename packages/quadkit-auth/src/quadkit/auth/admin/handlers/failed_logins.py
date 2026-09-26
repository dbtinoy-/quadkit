"""Failed logins widget handler."""

from __future__ import annotations

from quadkit.auth.services.activity_tracker import AuthActivityTracker
from quadkit.contracts.admin import Stat, StatContent, Tone, WidgetParams
from quadkit.contracts.admin.errors import AdminError
from quadkit.result import Ok, Result


class FailedLoginsWidgetHandler:
    """Handler for the failed logins widget.

    Args:
        tracker: injected AuthActivityTracker.
    """

    def __init__(self, tracker: AuthActivityTracker) -> None:
        """Initialize handler with the activity tracker.

        Args:
            tracker: AuthActivityTracker for login failure tracking.
        """
        self._tracker = tracker

    async def get_data(self, params: WidgetParams) -> Result[StatContent, AdminError]:
        """Fetch failed login statistics.

        Mirrors the widget template: a single ``is_elevated`` boundary gates
        the danger tone (the template's ``{% if is_elevated %}`` badge), with
        neutral styling otherwise. No multi-tier threshold ladder exists.

        Infrastructure failures propagate as exceptions.

        Args:
            params: Widget parameters (includes time_window_minutes).

        Returns:
            Result containing StatContent or AdminError.
        """
        window = getattr(params, "time_window_minutes", 30)
        count, unique_ips = self._tracker.failed_login_summary(
            window_minutes=int(window or 30)
        )
        return Ok(
            self._build_content(
                count=count, unique_ips=unique_ips, is_elevated=count > 0
            )
        )

    def _build_content(
        self, count: int, unique_ips: int, is_elevated: bool
    ) -> StatContent:
        """Build the StatContent mirroring the widget template.

        Args:
            count: Number of failed login attempts over the window.
            unique_ips: Number of unique source IPs.
            is_elevated: Whether the count is above the elevated threshold.

        Returns:
            StatContent with a danger tone when elevated and neutral styling
            otherwise, plus a conditional unique-IP stat.
        """
        tone = Tone.DANGER if is_elevated else Tone.DEFAULT
        stats: list[Stat] = [
            Stat(label="Failed Logins (1 hour)", value=str(count), tone=tone),
        ]
        if unique_ips > 0:
            stats.append(Stat(label="Unique IPs", value=str(unique_ips)))
        return StatContent(stats=tuple(stats))


__all__ = ["FailedLoginsWidgetHandler"]
