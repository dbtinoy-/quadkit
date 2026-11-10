"""Local time outputs never infer an offset, date, or ambiguous fold."""

from datetime import UTC, datetime, time, tzinfo
from uuid import uuid4

import pytest
from quadkit.result import Ok
from use_case_output_support import generate


@pytest.mark.parametrize(
    ("stored", "expected"),
    [
        (time.min, "00:00:00"),
        (time.max, "23:59:59.999999"),
        (time(12, 30), "12:30:00"),
        ("12:30:00.123", "12:30:00.123000"),
        ("12:30:00.000000", "12:30:00"),
        (None, None),
    ],
)
async def test_time_projection(tmp_path, monkeypatch, stored, expected):
    module = generate(
        tmp_path,
        monkeypatch,
        [
            {
                "name": "opens",
                "type": "time",
                "source": "aggregate.opens",
                "required": False,
            }
        ],
    )

    class Repository:
        async def get(self, key):
            return Ok({"opens": stored})

        async def update(self, key, values):
            return Ok(values)

    result = await module.PublishHandler(Repository()).handle(
        module.PublishCommand(title="new").for_aggregate(uuid4())
    )
    assert result.success, result.message
    assert result.output.opens == expected


class NoOffset(tzinfo):
    def utcoffset(self, dt):
        pytest.fail("local time projection must not consult timezone rules")


class TimeSubclass(time):
    pass


@pytest.mark.parametrize(
    "stored",
    [
        "120000",
        "12:00",
        "24:00:00",
        "12:00:60",
        "12:00:00.1234567",
        "12:00:00Z",
        "12:00:00+09:00",
        time(12, tzinfo=UTC),
        time(12, fold=1),
        time(12, tzinfo=NoOffset()),
        TimeSubclass(12),
        datetime(2025, 1, 1, tzinfo=UTC),
        True,
        1,
        b"12:00:00",
        None,
    ],
)
async def test_invalid_time_output_prevents_persistence(tmp_path, monkeypatch, stored):
    module = generate(
        tmp_path,
        monkeypatch,
        [{"name": "opens", "type": "time", "source": "aggregate.opens"}],
    )

    class Repository:
        writes = 0

        async def get(self, key):
            return Ok({"opens": stored})

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


@pytest.mark.parametrize("value", [time(12, tzinfo=UTC), time(12, fold=1)])
async def test_output_bound_time_input_fails_before_reads_without_sql_write(
    tmp_path, monkeypatch, value
):
    module = generate(
        tmp_path,
        monkeypatch,
        [{"name": "opens", "type": "time", "source": "input.opens"}],
        fields_str="title:str,opens:time",
    )

    class Repository:
        async def get(self, key):
            pytest.fail("invalid local time reached repository")

    result = await module.PublishHandler(Repository()).handle(
        module.PublishCommand(title="new", opens=value).for_aggregate(uuid4())
    )
    assert not result.success
    assert result.code == "invalid_input"


async def test_wire_time_requires_canonical_spelling(tmp_path, monkeypatch):
    module = generate(
        tmp_path,
        monkeypatch,
        [{"name": "opens", "type": "time", "source": "aggregate.opens"}],
    )
    for value in ("12:00:00.123", "12:00:00.000000"):
        with pytest.raises(ValueError, match="canonical"):
            module.PublishOutput(opens=value)


@pytest.mark.parametrize("value", [time.min, time.max, time(12, 30, 1, 123000)])
async def test_typed_time_input_projects_before_read(tmp_path, monkeypatch, value):
    module = generate(
        tmp_path,
        monkeypatch,
        [{"name": "opens", "type": "time", "source": "input.opens"}],
        fields_str="title:str,opens:time",
    )

    class Repository:
        async def get(self, key):
            return Ok({})

        async def update(self, key, values):
            return Ok(values)

    result = await module.PublishHandler(Repository()).handle(
        module.PublishCommand(title="new", opens=value).for_aggregate(uuid4())
    )
    assert result.success, result.message
    assert result.output.opens == value.isoformat()


async def test_repeated_time_source_normalizes_once(tmp_path, monkeypatch):
    module = generate(
        tmp_path,
        monkeypatch,
        [
            {
                "name": "first",
                "type": "time",
                "source": "input.opens",
                "required": False,
            },
            {"name": "second", "type": "time", "source": "input.opens"},
        ],
        fields_str="title:str,opens:time",
    )
    original = module._project_time
    calls = []

    def tracked(value):
        if type(value) is time:
            calls.append(value)
        return original(value)

    monkeypatch.setattr(module, "_project_time", tracked)

    class Repository:
        async def get(self, key):
            return Ok({})

        async def update(self, key, values):
            return Ok(values)

    value = time(12)
    result = await module.PublishHandler(Repository()).handle(
        module.PublishCommand(title="new", opens=value).for_aggregate(uuid4())
    )
    assert result.success, result.message
    assert result.output.first == result.output.second == "12:00:00"
    assert calls == [value]
