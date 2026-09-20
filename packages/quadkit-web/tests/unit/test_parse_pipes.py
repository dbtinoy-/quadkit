"""Unit tests for the builtin parse pipes (pure transform logic)."""

from __future__ import annotations

from datetime import datetime
import uuid

import pytest

from quadkit.web.pipes.builtin.parse import (
    DefaultValuePipe,
    ParseBoolPipe,
    ParseDatePipe,
    ParseIntPipe,
    ParseUUIDPipe,
)
from quadkit.web.protocols import ParamMetadata


def _meta(name: str = "p", default=None, ptype: str = "query") -> ParamMetadata:
    return ParamMetadata(name=name, param_type=ptype, default=default)


class TestParseIntPipe:
    async def test_parse(self) -> None:
        assert await ParseIntPipe().transform("42", _meta()) == 42
        assert await ParseIntPipe().transform(" -7 ", _meta()) == -7
        assert await ParseIntPipe().transform(3, _meta()) == 3

    async def test_invalid_strict_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid integer"):
            await ParseIntPipe().transform("abc", _meta("n"))

    async def test_invalid_non_strict_default(self) -> None:
        pipe = ParseIntPipe(strict=False)
        assert await pipe.transform("abc", _meta(default="5")) == 5
        assert await pipe.transform("abc", _meta()) == 0

    async def test_missing(self) -> None:
        with pytest.raises(ValueError, match="Missing required"):
            await ParseIntPipe().transform(None, _meta("n"))
        assert await ParseIntPipe().transform(None, _meta(default="9")) == 9
        assert await ParseIntPipe(strict=False).transform(None, _meta()) == 0


class TestParseUUIDPipe:
    async def test_parse(self) -> None:
        u = uuid.uuid4()
        assert await ParseUUIDPipe().transform(str(u), _meta()) == u
        assert await ParseUUIDPipe().transform(u, _meta()) == u

    async def test_invalid(self) -> None:
        with pytest.raises(ValueError, match="Invalid UUID"):
            await ParseUUIDPipe().transform("nope", _meta("id"))

    async def test_missing(self) -> None:
        with pytest.raises(ValueError, match="Missing required"):
            await ParseUUIDPipe().transform(None, _meta("id"))
        u = uuid.uuid4()
        assert await ParseUUIDPipe().transform(None, _meta(default=str(u))) == u


class TestParseBoolPipe:
    async def test_true_values(self) -> None:
        for v in ["true", "1", "yes", "on", "TRUE", " Yes "]:
            assert await ParseBoolPipe().transform(v, _meta()) is True

    async def test_false_values(self) -> None:
        for v in ["false", "0", "no", "off", "FALSE"]:
            assert await ParseBoolPipe().transform(v, _meta()) is False

    async def test_passthrough_bool(self) -> None:
        assert await ParseBoolPipe().transform(True, _meta()) is True
        assert await ParseBoolPipe().transform(False, _meta()) is False

    async def test_missing_uses_default(self) -> None:
        assert await ParseBoolPipe().transform(None, _meta(default=False)) is False
        assert await ParseBoolPipe().transform(None, _meta()) is True

    async def test_ambiguous_falls_back_to_default(self) -> None:
        assert await ParseBoolPipe().transform("maybe", _meta(default=True)) is True
        assert await ParseBoolPipe().transform("maybe", _meta(default=0)) is False


class TestParseDatePipe:
    async def test_iso_formats(self) -> None:
        assert (
            await ParseDatePipe().transform("2026-09-13", _meta())
            == datetime(2026, 9, 13)
        )
        assert (
            await ParseDatePipe().transform("2026-09-13T10:30:00", _meta())
            == datetime(2026, 9, 13, 10, 30)
        )
        assert (
            await ParseDatePipe().transform("2026-09-13 10:30:00", _meta())
            == datetime(2026, 9, 13, 10, 30)
        )
        assert (
            await ParseDatePipe().transform("2026/09/13", _meta())
            == datetime(2026, 9, 13)
        )

    async def test_datetime_passthrough(self) -> None:
        dt = datetime(2020, 1, 2, 3)
        assert await ParseDatePipe().transform(dt, _meta()) is dt

    async def test_default_and_missing(self) -> None:
        dt = datetime(2020, 1, 2)
        assert (await ParseDatePipe().transform(None, _meta(default=dt))) == dt
        assert (
            await ParseDatePipe().transform(None, _meta(default="2020-01-02"))
            == datetime(2020, 1, 2)
        )
        with pytest.raises(ValueError, match="Missing required"):
            await ParseDatePipe().transform(None, _meta("d"))

    async def test_invalid(self) -> None:
        with pytest.raises(ValueError, match="Invalid date"):
            await ParseDatePipe().transform("13/09/2026", _meta("d"))


class TestDefaultValuePipe:
    async def test_applies_default_when_none(self) -> None:
        assert await DefaultValuePipe(default=7).transform(None, _meta()) == 7
        assert await DefaultValuePipe().transform(None, _meta()) is None

    async def test_passes_value_through(self) -> None:
        assert await DefaultValuePipe(default=7).transform("x", _meta()) == "x"
