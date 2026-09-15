"""Server status widget — real process info."""

from __future__ import annotations

import platform

from quadkit.contracts.admin import Tone, WidgetParams
from quadkit.result import Ok
from quadkit.web.admin.handlers.server_status import ServerStatusWidgetHandler


async def test_server_status_reports_python_version() -> None:
    handler = ServerStatusWidgetHandler()
    result = await handler.get_data(WidgetParams(time_window_minutes=60))
    assert isinstance(result, Ok)
    values = [s.value for s in result.unwrap().stats]
    assert platform.python_version() in "".join(values)


async def test_server_status_mirrors_template_rows() -> None:
    result = await ServerStatusWidgetHandler().get_data(WidgetParams())
    stats = result.unwrap().stats
    assert [s.label for s in stats] == ["Python", "Process Uptime (s)", "Threads"]
    assert stats[2].tone is Tone.INFO


async def test_server_status_reports_non_negative_uptime() -> None:
    result = await ServerStatusWidgetHandler().get_data(WidgetParams())
    stats = result.unwrap().stats
    uptime = stats[1]
    assert int(uptime.value.replace(",", "")) >= 0


__all__ = [
    "test_server_status_mirrors_template_rows",
    "test_server_status_reports_non_negative_uptime",
    "test_server_status_reports_python_version",
]