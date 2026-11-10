"""Authored output projections remain typed, explicit and persistence-safe."""

import importlib.util
import sys
from typing import get_type_hints
from uuid import UUID, uuid4

import pytest
from quadkit.events.cli.generators.use_case import UseCaseGenerator
from quadkit.result import Ok
from use_case_output_support import generate


async def test_projects_only_authored_fields(tmp_path, monkeypatch):
    module = generate(
        tmp_path,
        monkeypatch,
        [
            {
                "name": "title",
                "type": "str",
                "source": "aggregate.title",
                "required": True,
            },
            {
                "name": "note",
                "type": "str",
                "source": "aggregate.note",
                "required": False,
            },
            {
                "name": "requested",
                "type": "str",
                "source": "input.title",
                "required": True,
            },
        ],
    )

    class Repository:
        async def get(self, key):
            return Ok({"title": "old", "secret": "never disclose", "note": None})

        async def update(self, key, values):
            return Ok(values)

    result = await module.PublishHandler(Repository()).handle(
        module.PublishCommand(title="new").for_aggregate(uuid4())
    )
    assert result.success
    assert result.output == module.PublishOutput(
        title="new", note=None, requested="new"
    )
    assert not hasattr(result.output, "secret")


async def test_invalid_projection_prevents_write(tmp_path, monkeypatch):
    module = generate(
        tmp_path,
        monkeypatch,
        [
            {
                "name": "count",
                "type": "int",
                "source": "aggregate.count",
                "required": True,
            }
        ],
    )

    class Repository:
        writes = 0

        async def get(self, key):
            return Ok({"count": True})

        async def update(self, key, values):
            self.writes += 1
            return Ok(values)

    repo = Repository()
    result = await module.PublishHandler(repo).handle(
        module.PublishCommand(title="new").for_aggregate(uuid4())
    )
    assert not result.success
    assert result.code == "invalid_output"
    assert result.output is None
    assert repo.writes == 0


@pytest.mark.parametrize(
    "field",
    [
        {"name": "bad-name", "type": "str", "source": "input.title"},
        {"name": "model_dump", "type": "str", "source": "input.title"},
        {"name": "title", "type": "json", "source": "input.title"},
        {"name": "title", "type": "str", "source": "input.missing"},
        {"name": "title", "type": "str", "source": "aggregate.x()"},
        {"name": "title", "type": "int", "source": "input.title"},
        {"name": "title", "type": "str", "source": "principal"},
        {"name": "title", "type": "str", "source": "input.title", "required": "false"},
    ],
)
def test_refuses_unsupported_projection_even_in_dry_run(tmp_path, field):
    with pytest.raises(ValueError, match="output"):
        UseCaseGenerator(tmp_path).generate(
            "publish",
            fields_str="title:str",
            spec={"output_fields": [field]},
            dry_run=True,
        )
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize(
    ("kind", "value"),
    [
        ("float", float("nan")),
        ("float", float("inf")),
        ("str", "\ud800"),
        ("int", 10**4500),
        ("str", None),
        ("bool", 1),
    ],
    ids=[
        "nan",
        "infinite",
        "surrogate",
        "oversized-integer",
        "missing",
        "bool-is-not-int",
    ],
)
async def test_unserializable_or_mistyped_output_never_writes(
    tmp_path, monkeypatch, kind, value
):
    module = generate(
        tmp_path,
        monkeypatch,
        [{"name": "value", "type": kind, "source": "aggregate.value"}],
    )

    class Repository:
        async def get(self, key):
            return Ok({"value": value})

        async def update(self, key, values):
            pytest.fail("invalid output must be rejected before persistence")

    result = await module.PublishHandler(Repository()).handle(
        module.PublishCommand(title="new").for_aggregate(uuid4())
    )
    assert not result.success
    assert result.code == "invalid_output"
    assert result.output is None


@pytest.mark.parametrize(
    "raw",
    [
        {},
        "title",
        [None],
        [{}],
        [{"name": "self", "type": "str", "source": "input.title"}],
        [{"name": "title", "type": [], "source": "input.title"}],
    ],
)
def test_output_shape_is_explicit(tmp_path, raw):
    with pytest.raises((ValueError, TypeError), match="output"):
        UseCaseGenerator(tmp_path).generate(
            "publish", fields_str="title:str", spec={"output_fields": raw}
        )
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize(
    "stored",
    [
        "abcdefab-1234-5678-1234-567812345678",
        UUID("abcdefab-1234-5678-1234-567812345678"),
        None,
    ],
)
async def test_uuid_projection_emits_canonical_wire_string(
    tmp_path, monkeypatch, stored
):
    module = generate(
        tmp_path,
        monkeypatch,
        [
            {
                "name": "owner",
                "type": "uuid",
                "source": "aggregate.owner",
                "required": False,
            }
        ],
    )

    class Repository:
        async def get(self, key):
            return Ok({"owner": stored, "title": "old"})

        async def update(self, key, values):
            return Ok(values)

    result = await module.PublishHandler(Repository()).handle(
        module.PublishCommand(title="new").for_aggregate(uuid4())
    )
    assert result.success, result.message
    assert result.output.owner == (str(stored) if stored is not None else None)
    assert get_type_hints(module._project_uuid)["return"] is str
    assert get_type_hints(module._project_nullable_uuid)["return"] == str | None


@pytest.mark.parametrize(
    "stored",
    [
        "bad",
        "ABCDEFAB-1234-5678-1234-567812345678",
        "abcdefab123456781234567812345678",
        True,
        1,
        b"bad",
        None,
    ],
)
async def test_invalid_uuid_output_prevents_persistence(tmp_path, monkeypatch, stored):
    module = generate(
        tmp_path,
        monkeypatch,
        [{"name": "owner", "type": "uuid", "source": "aggregate.owner"}],
    )

    class Repository:
        writes = 0

        async def get(self, key):
            return Ok({"owner": stored, "title": "old"})

        async def update(self, key, values):
            self.writes += 1
            return Ok(values)

    repo = Repository()
    result = await module.PublishHandler(repo).handle(
        module.PublishCommand(title="new").for_aggregate(uuid4())
    )
    assert not result.success
    assert result.code == "invalid_output"
    assert result.output is None
    assert repo.writes == 0
    with pytest.raises(ValueError, match=r"invalid output field|UUID|uuid"):
        module.PublishOutput(owner=stored)


async def test_typed_uuid_input_projects_to_wire_string(tmp_path, monkeypatch):
    UseCaseGenerator(tmp_path).generate(
        "assign",
        fields_str="owner:uuid",
        spec={
            "typed_outcomes": True,
            "validate_inputs": True,
            "writes": [{"field": "owner", "source": "input.owner"}],
            "output_fields": [
                {"name": "owner", "type": "uuid", "source": "input.owner"}
            ],
        },
    )
    spec = importlib.util.spec_from_file_location(
        "uuid_input_output", tmp_path / "assign_use_case.py"
    )
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)

    class Repository:
        async def get(self, key):
            return Ok({"owner": None})

        async def update(self, key, values):
            return Ok(values)

    value = uuid4()
    result = await module.AssignHandler(Repository()).handle(
        module.AssignCommand(owner=value).for_aggregate(uuid4())
    )
    assert result.success, result.message
    assert result.output.owner == str(value)
