"""Unit tests for quadkit.primitives.clock.today()."""

from __future__ import annotations

from datetime import UTC, date, datetime

from quadkit.primitives import clock


class _FixedClock:
    def __init__(self, instant: datetime) -> None:
        self._instant = instant

    def now(self) -> datetime:
        return self._instant

    def monotonic(self) -> float:
        return 0.0

    def timestamp(self) -> float:
        return self._instant.timestamp()

    def time(self) -> float:
        return self._instant.timestamp()


def test_today_follows_ambient_clock_across_utc_midnight() -> None:
    before_midnight = _FixedClock(datetime(2026, 10, 24, 23, 59, 59, tzinfo=UTC))
    after_midnight = _FixedClock(datetime(2026, 10, 25, 0, 0, 1, tzinfo=UTC))

    with clock.use(before_midnight):
        assert clock.today() == date(2026, 10, 24)

    with clock.use(after_midnight):
        assert clock.today() == date(2026, 10, 25)


async def test_config_provider_supports_section_base_config_alongside_quadkit_config() -> (
    None
):
    from dataclasses import dataclass
    from typing import ClassVar

    from quadkit import Application
    from quadkit.config import BaseConfig, QuadkitConfig
    from quadkit.config.di.provider import ConfigProvider
    from quadkit.contracts.core.config import ConfigProtocol

    @dataclass(init=False, eq=False, kw_only=True)
    class _SampleAppSection(BaseConfig):
        config_section: ClassVar[str] = "sample_app"
        max_items: int = 25

    qcfg = QuadkitConfig.model_validate({"sample_app": {"max_items": 99}})
    app = Application(name="sample-test", config=qcfg)

    provider = ConfigProvider(config_class=_SampleAppSection)
    await provider.register(app.container)

    resolved = await app.container.resolve(_SampleAppSection)
    assert resolved.max_items == 99
    assert await app.container.resolve(ConfigProtocol) is qcfg
