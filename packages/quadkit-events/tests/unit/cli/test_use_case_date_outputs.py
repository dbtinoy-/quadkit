"""Date projections are canonical wire strings, never datetime coercions."""

from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from quadkit.result import Ok
from use_case_output_support import generate


@pytest.mark.parametrize(
    "stored", [date(2024, 2, 29), "2024-02-29", date.min, date.max, None]
)
async def test_date_projection(tmp_path, monkeypatch, stored):
    module = generate(
        tmp_path,
        monkeypatch,
        [{"name": "due", "type": "date", "source": "aggregate.due", "required": False}],
    )

    class Repository:
        async def get(self, key):
            return Ok({"due": stored})

        async def update(self, key, values):
            return Ok(values)

    result = await module.PublishHandler(Repository()).handle(
        module.PublishCommand(title="new").for_aggregate(uuid4())
    )
    assert result.success, result.message
    assert result.output.due == (str(stored) if stored is not None else None)


@pytest.mark.parametrize(
    "stored",
    [
        "2025-02-29",
        "20240229",
        "2024-W09-4",
        "2024-02-29T00:00:00",
        datetime(2024, 2, 29, tzinfo=UTC),
        True,
        1,
        None,
    ],
)
async def test_invalid_date_output_prevents_persistence(tmp_path, monkeypatch, stored):
    module = generate(
        tmp_path,
        monkeypatch,
        [{"name": "due", "type": "date", "source": "aggregate.due"}],
    )

    class Repository:
        writes = 0

        async def get(self, key):
            return Ok({"due": stored})

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
    with pytest.raises(ValueError, match=r"[Ii]nvalid|range|format"):
        module.PublishOutput(due=stored)


async def test_typed_date_input_projects_to_wire_string(tmp_path, monkeypatch):
    module = generate(
        tmp_path,
        monkeypatch,
        [{"name": "due", "type": "date", "source": "input.due"}],
        fields_str="title:str,due:date",
    )

    class Repository:
        async def get(self, key):
            return Ok({})

        async def update(self, key, values):
            return Ok(values)

    result = await module.PublishHandler(Repository()).handle(
        module.PublishCommand(title="new", due=date(2024, 2, 29)).for_aggregate(uuid4())
    )
    assert result.success, result.message
    assert result.output.due == "2024-02-29"
