"""Datetime projections preserve instants, require offsets and emit UTC RFC3339."""

from datetime import UTC, date, datetime, timedelta, timezone, tzinfo
from uuid import uuid4

import pytest
from quadkit.result import Ok
from use_case_output_support import generate


@pytest.mark.parametrize(
    ("stored", "expected"),
    [
        (
            datetime(2025, 1, 1, 9, tzinfo=timezone(timedelta(hours=9))),
            "2025-01-01T00:00:00Z",
        ),
        ("2025-01-01 09:00:00+09:00", "2025-01-01T00:00:00Z"),
        ("2025-01-01T00:00:00.123Z", "2025-01-01T00:00:00.123000Z"),
        ("2024-12-31T19:00:00-05:00", "2025-01-01T00:00:00Z"),
        (None, None),
    ],
)
async def test_datetime_projection(tmp_path, monkeypatch, stored, expected):
    module = generate(
        tmp_path,
        monkeypatch,
        [
            {
                "name": "scheduled",
                "type": "datetime",
                "source": "aggregate.scheduled",
                "required": False,
            }
        ],
    )

    class Repository:
        async def get(self, key):
            return Ok({"scheduled": stored})

        async def update(self, key, values):
            return Ok(values)

    result = await module.PublishHandler(Repository()).handle(
        module.PublishCommand(title="new").for_aggregate(uuid4())
    )
    assert result.success, result.message
    assert result.output.scheduled == expected


class BrokenOffset(tzinfo):
    def utcoffset(self, dt):
        raise RuntimeError("broken timezone callback")


@pytest.mark.parametrize(
    "stored",
    [
        datetime(2025, 1, 1),
        date(2025, 1, 1),
        "2025-01-01T00:00:00",
        "2025-01-01",
        "20250101T000000Z",
        "2025-W01-3T00:00:00Z",
        "2025-01-01T00:00:60Z",
        "2025-01-01T00:00:00-00:00",
        "2025-01-01T00:00:00+00:60",
        "2025-01-01T00:00:00.1234567Z",
        True,
        1,
        None,
        datetime(1, 1, 1, tzinfo=timezone(timedelta(hours=1))),
        datetime(2025, 1, 1, tzinfo=BrokenOffset()),
    ],
)
async def test_invalid_datetime_output_prevents_persistence(
    tmp_path, monkeypatch, stored
):
    module = generate(
        tmp_path,
        monkeypatch,
        [{"name": "scheduled", "type": "datetime", "source": "aggregate.scheduled"}],
    )

    class Repository:
        writes = 0

        async def get(self, key):
            return Ok({"scheduled": stored})

        async def update(self, key, values):
            self.writes += 1
            return Ok(values)

    repo = Repository()
    result = await module.PublishHandler(repo).handle(
        module.PublishCommand(title="new").for_aggregate(uuid4())
    )
    assert not result.success
    assert result.code == "invalid_output"
    assert repo.writes == 0


async def test_wire_dto_requires_canonical_utc(tmp_path, monkeypatch):
    module = generate(
        tmp_path,
        monkeypatch,
        [{"name": "scheduled", "type": "datetime", "source": "aggregate.scheduled"}],
    )
    for value in (
        "2025-01-01T09:00:00+09:00",
        "2025-01-01T00:00:00+00:00",
        "2025-01-01T00:00:00.123Z",
    ):
        with pytest.raises(ValueError, match="canonical"):
            module.PublishOutput(scheduled=value)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (datetime.min.replace(tzinfo=UTC), "0001-01-01T00:00:00Z"),
        (datetime.max.replace(tzinfo=UTC), "9999-12-31T23:59:59.999999Z"),
        (
            datetime(2025, 1, 1, 0, 0, 30, tzinfo=timezone(timedelta(seconds=30))),
            "2025-01-01T00:00:00Z",
        ),
    ],
)
async def test_typed_datetime_input_projects_to_wire_string(
    tmp_path, monkeypatch, value, expected
):
    module = generate(
        tmp_path,
        monkeypatch,
        [{"name": "scheduled", "type": "datetime", "source": "input.scheduled"}],
        fields_str="title:str,scheduled:datetime",
    )

    class Repository:
        async def get(self, key):
            return Ok({})

        async def update(self, key, values):
            return Ok(values)

    result = await module.PublishHandler(Repository()).handle(
        module.PublishCommand(title="new", scheduled=value).for_aggregate(uuid4())
    )
    assert result.success, result.message
    assert result.output.scheduled == expected


async def test_native_iso_offset_seconds_are_normalized(tmp_path, monkeypatch):
    module = generate(
        tmp_path,
        monkeypatch,
        [{"name": "scheduled", "type": "datetime", "source": "aggregate.scheduled"}],
    )
    assert (
        module._project_datetime("2025-01-01T00:00:30+00:00:30")
        == "2025-01-01T00:00:00Z"
    )


@pytest.mark.parametrize(
    "value",
    [
        datetime(2025, 1, 1),
        datetime(1, 1, 1, tzinfo=timezone(timedelta(hours=1))),
        datetime(2025, 1, 1, tzinfo=BrokenOffset()),
    ],
)
async def test_output_bound_datetime_input_fails_before_read_without_sql_write(
    tmp_path, monkeypatch, value
):
    module = generate(
        tmp_path,
        monkeypatch,
        [{"name": "scheduled", "type": "datetime", "source": "input.scheduled"}],
        fields_str="title:str,scheduled:datetime",
    )

    class Repository:
        async def get(self, key):
            pytest.fail("invalid client instant reached repository")

    result = await module.PublishHandler(Repository()).handle(
        module.PublishCommand(title="new", scheduled=value).for_aggregate(uuid4())
    )
    assert not result.success
    assert result.code == "invalid_input"


async def test_repeated_input_projection_normalizes_typed_value_once(
    tmp_path, monkeypatch
):
    module = generate(
        tmp_path,
        monkeypatch,
        [
            {
                "name": "first",
                "type": "datetime",
                "source": "input.scheduled",
                "required": False,
            },
            {"name": "second", "type": "datetime", "source": "input.scheduled"},
        ],
        fields_str="title:str,scheduled:datetime",
    )
    original = module._project_datetime
    calls = []

    def tracked(value):
        if type(value) is datetime:
            calls.append(value)
        return original(value)

    monkeypatch.setattr(module, "_project_datetime", tracked)

    class Repository:
        async def get(self, key):
            return Ok({})

        async def update(self, key, values):
            return Ok(values)

    value = datetime(2025, 1, 1, tzinfo=UTC)
    result = await module.PublishHandler(Repository()).handle(
        module.PublishCommand(title="new", scheduled=value).for_aggregate(uuid4())
    )
    assert result.success, result.message
    assert result.output.first == result.output.second == "2025-01-01T00:00:00Z"
    assert calls == [value]
