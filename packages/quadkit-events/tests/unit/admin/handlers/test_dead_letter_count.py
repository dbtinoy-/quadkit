"""Dead-letter count widget reads the bus's dead-letter store."""

from __future__ import annotations

from quadkit.contracts.admin import StatContent, Tone, WidgetParams
from quadkit.events.admin.handlers.dead_letter_count import (
    DeadLetterCountWidgetHandler,
)
from quadkit.result import Ok


class _FakeDeadLetterStore:
    def __init__(self, count: int) -> None:
        self._count = count

    async def list_entries(self, limit: int = 100) -> list:
        return [object() for _ in range(min(self._count, limit))]


class _FakeBus:
    def __init__(self, store: object | None = None) -> None:
        self.dead_letter_store = store


async def test_dead_letter_count_reads_real_store() -> None:
    handler = DeadLetterCountWidgetHandler(_FakeBus(_FakeDeadLetterStore(3)))
    result = await handler.get_data(WidgetParams(time_window_minutes=60))
    assert isinstance(result, Ok)
    values = [s.value for s in result.unwrap().stats]
    assert any("3" in v for v in values)


async def test_dead_letter_count_degrades_without_store() -> None:
    handler = DeadLetterCountWidgetHandler(_FakeBus(None))
    result = await handler.get_data(WidgetParams(time_window_minutes=60))
    assert isinstance(result, Ok)
    values = [s.value for s in result.unwrap().stats]
    assert any("clear" in v.lower() for v in values)


async def test_dead_letter_count_handler_returns_stat_content() -> None:
    result = await DeadLetterCountWidgetHandler(
        event_bus=_FakeBus(_FakeDeadLetterStore(0))
    ).get_data(WidgetParams())
    content = result.unwrap()
    assert isinstance(content, StatContent)
    assert content.stats[0].value == "✓ Queue clear"
    assert content.stats[0].tone is Tone.SUCCESS


__all__ = [
    "test_dead_letter_count_degrades_without_store",
    "test_dead_letter_count_handler_returns_stat_content",
    "test_dead_letter_count_reads_real_store",
]