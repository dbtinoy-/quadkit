"""Request rate widget — reads registered metrics when present."""

from __future__ import annotations

from quadkit.contracts.admin import WidgetParams
from quadkit.result import Ok
from quadkit.web.admin.handlers.request_rate import RequestRateWidgetHandler


class _FakeMetric:
    def __init__(self, value: float) -> None:
        self._value = value

    def get_value(self) -> float:
        return self._value


class _FakeMetrics:
    def get_metric(self, name: str) -> object | None:
        return _FakeMetric(42.0) if name == "http_requests_total" else None

    def get_all_metrics(self) -> dict[str, object]:
        return {}


async def test_request_rate_reads_metrics_backend() -> None:
    handler = RequestRateWidgetHandler(_FakeMetrics())
    result = await handler.get_data(WidgetParams(time_window_minutes=60))
    assert isinstance(result, Ok)
    values = [s.value for s in result.unwrap().stats]
    assert any("42" in v for v in values)


async def test_request_rate_degrades_when_no_metrics() -> None:
    result = await RequestRateWidgetHandler().get_data(WidgetParams())
    values = [s.value for s in result.unwrap().stats]
    assert "Not measured" in values


__all__ = [
    "test_request_rate_degrades_when_no_metrics",
    "test_request_rate_reads_metrics_backend",
]