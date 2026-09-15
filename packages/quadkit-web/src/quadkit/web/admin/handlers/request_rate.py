"""Request rate widget handler for web admin dashboard."""

from __future__ import annotations

from quadkit.contracts.admin import (
    MetricsReadbackProtocol,
    Stat,
    StatContent,
    Tone,
    WidgetParams,
)
from quadkit.contracts.admin.errors import AdminError
from quadkit.result import Ok, Result

_METRIC_COUNTER = "http_requests_total"


class RequestRateWidgetHandler:
    """Handler for the request_rate widget.

    Args:
        metrics: optional metrics readback source; when absent or lacking the
            readback capability, the widget degrades to "Not measured".
    """

    def __init__(self, metrics: MetricsReadbackProtocol | None = None) -> None:
        self._metrics = metrics

    async def get_data(self, params: WidgetParams) -> Result[StatContent, AdminError]:
        """Fetch request rate data.

        Args:
            params: Widget request parameters (unused for this widget).

        Returns:
            Result containing StatContent with request metrics.
        """
        if not isinstance(self._metrics, MetricsReadbackProtocol):
            return Ok(
                StatContent(
                    stats=(
                        Stat(
                            label="Requests/sec",
                            value="Not measured",
                            tone=Tone.WARNING,
                        ),
                    )
                )
            )
        metric = self._metrics.get_metric(_METRIC_COUNTER)
        get_value = getattr(metric, "get_value", None)
        value = (
            get_value
            if callable(get_value)
            else getattr(metric, "get_count", lambda: 0.0)
        )
        return Ok(
            StatContent(
                stats=(Stat(label="Requests/sec", value=f"{float(value()):.1f}"),)
            )
        )


__all__ = ["RequestRateWidgetHandler"]
