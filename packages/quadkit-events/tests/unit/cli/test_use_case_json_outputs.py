"""JSON outputs retain native JSON-object semantics and detached snapshots."""

from datetime import date
from uuid import uuid4

import pytest
from quadkit.result import Ok
from use_case_output_support import generate


def cyclic_object():
    value = {}
    value["self"] = value
    return value


class DictSubclass(dict):
    def __deepcopy__(self, memo):
        pytest.fail("must validate JSON before any deepcopy callback")


INVALID = [
    None,
    [],
    "{}",
    True,
    1,
    {1: "bad"},
    {"x": (1, 2)},
    {"x": {1, 2}},
    {"x": date(2025, 1, 1)},
    {"x": b"bytes"},
    {"x": float("nan")},
    {"x": float("inf")},
    {"x": "\ud800"},
    {"\ud800": "bad"},
    {"x": DictSubclass()},
    DictSubclass(),
    cyclic_object(),
]


@pytest.mark.parametrize(
    "value", [{}, {"items": [1, 1.5, False, None, {"label": "안녕"}]}, {"nul": "\0"}]
)
async def test_json_projection_is_a_detached_snapshot(tmp_path, monkeypatch, value):
    module = generate(
        tmp_path,
        monkeypatch,
        [{"name": "details", "type": "json", "source": "aggregate.details"}],
    )

    class Repository:
        async def get(self, key):
            return Ok({"details": value})

        async def update(self, key, values):
            value["after_projection"] = True
            return Ok(values)

    expected = value.copy()
    result = await module.PublishHandler(Repository()).handle(
        module.PublishCommand(title="new").for_aggregate(uuid4())
    )
    assert result.success, result.message
    assert result.output.details == expected
    assert result.output.details is not value


@pytest.mark.parametrize("value", INVALID)
async def test_invalid_stored_json_refuses_writes(tmp_path, monkeypatch, value):
    module = generate(
        tmp_path,
        monkeypatch,
        [{"name": "details", "type": "json", "source": "aggregate.details"}],
    )

    class Repository:
        async def get(self, key):
            return Ok({"details": value})

        async def update(self, key, values):
            pytest.fail("invalid projection must not persist")

    result = await module.PublishHandler(Repository()).handle(
        module.PublishCommand(title="new").for_aggregate(uuid4())
    )
    assert not result.success
    assert result.code == "invalid_output"


@pytest.mark.parametrize("value", INVALID)
async def test_invalid_output_bound_json_input_refuses_reads(
    tmp_path, monkeypatch, value
):
    module = generate(
        tmp_path,
        monkeypatch,
        [{"name": "details", "type": "json", "source": "input.details"}],
        fields_str="title:str,details:json",
    )

    class Repository:
        async def get(self, key):
            pytest.fail("invalid input must not read")

        async def update(self, key, values):
            pytest.fail("invalid input must not persist")

    result = await module.PublishHandler(Repository()).handle(
        module.PublishCommand(title="new", details=value).for_aggregate(uuid4())
    )
    assert not result.success
    assert result.code == "invalid_input"


async def test_json_dto_clones_each_field_and_preserves_null_keys(
    tmp_path, monkeypatch
):
    module = generate(
        tmp_path,
        monkeypatch,
        [
            {"name": "details", "type": "json", "source": "aggregate.details"},
            {"name": "again", "type": "json", "source": "aggregate.details"},
            {
                "name": "optional",
                "type": "json",
                "source": "aggregate.optional",
                "required": False,
            },
        ],
    )
    shared = {"children": [{"ready": True}]}
    dto = module.PublishOutput(details=shared, again=shared, optional=None)
    shared["children"][0]["ready"] = False
    assert dto.details == dto.again == {"children": [{"ready": True}]}
    dto.details["children"][0]["ready"] = False
    assert dto.again == {"children": [{"ready": True}]}
    assert dto.optional is None
    for invalid in INVALID:
        with pytest.raises(ValueError, match=r"invalid.*output"):
            module.PublishOutput(details=invalid, again={}, optional=None)


async def test_shared_json_subtrees_are_valid_but_detached(tmp_path, monkeypatch):
    module = generate(
        tmp_path,
        monkeypatch,
        [{"name": "details", "type": "json", "source": "input.details"}],
        fields_str="title:str,details:json",
    )
    child = {"ready": True}
    value = {"first": child, "second": child}
    dto = module.PublishOutput(details=value)
    assert dto.details == value
    assert dto.details["first"] is not child
    assert dto.details["first"] is not dto.details["second"]


@pytest.mark.parametrize("value", [None, {"x": float("nan")}, cyclic_object()])
async def test_required_json_checks_cannot_be_disabled(tmp_path, monkeypatch, value):
    module = generate(
        tmp_path,
        monkeypatch,
        [{"name": "details", "type": "json", "source": "input.details"}],
        fields_str="title:str,details:json",
        validate_inputs=False,
    )

    class Repository:
        async def get(self, key):
            pytest.fail("output-bound JSON must be validated before reads")

    result = await module.PublishHandler(Repository()).handle(
        module.PublishCommand(title="new", details=value).for_aggregate(uuid4())
    )
    assert not result.success
    assert result.code == "invalid_input"


@pytest.mark.parametrize("value", [None, {}])
async def test_nullable_json_input_is_retained(tmp_path, monkeypatch, value):
    module = generate(
        tmp_path,
        monkeypatch,
        [
            {
                "name": "details",
                "type": "json",
                "source": "input.details",
                "required": False,
            }
        ],
        fields_str="title:str,details:json?",
    )

    class Repository:
        async def get(self, key):
            return Ok({})

        async def update(self, key, values):
            return Ok(values)

    result = await module.PublishHandler(Repository()).handle(
        module.PublishCommand(title="new", details=value).for_aggregate(uuid4())
    )
    assert result.success, result.message
    assert result.output.details == value


async def test_json_output_rejects_serializer_limits_without_recursion_failure(
    tmp_path, monkeypatch
):
    module = generate(
        tmp_path,
        monkeypatch,
        [{"name": "details", "type": "json", "source": "aggregate.details"}],
    )
    deep = {}
    cursor = deep
    for _ in range(2000):
        child = {}
        cursor["child"] = child
        cursor = child
    for value in (deep, {"huge": 10**5000}):
        with pytest.raises(ValueError, match="invalid JSON object output"):
            module.PublishOutput(details=value)


async def test_json_input_snapshot_precedes_repository_await(tmp_path, monkeypatch):
    module = generate(
        tmp_path,
        monkeypatch,
        [{"name": "details", "type": "json", "source": "input.details"}],
        fields_str="title:str,details:json",
    )
    value = {"items": [{"ready": True}]}

    class Repository:
        async def get(self, key):
            value["items"][0]["ready"] = False
            return Ok({})

        async def update(self, key, values):
            return Ok(values)

    result = await module.PublishHandler(Repository()).handle(
        module.PublishCommand(title="new", details=value).for_aggregate(uuid4())
    )
    assert result.success, result.message
    assert result.output.details == {"items": [{"ready": True}]}


async def test_deep_serializable_json_does_not_require_recursive_dataclass_copy(
    tmp_path, monkeypatch
):
    module = generate(
        tmp_path,
        monkeypatch,
        [{"name": "details", "type": "json", "source": "input.details"}],
        fields_str="title:str,details:json",
    )
    value = {}
    cursor = value
    for _ in range(350):
        child = {}
        cursor["child"] = child
        cursor = child

    class Repository:
        async def get(self, key):
            return Ok({})

        async def update(self, key, values):
            return Ok(values)

    result = await module.PublishHandler(Repository()).handle(
        module.PublishCommand(title="new", details=value).for_aggregate(uuid4())
    )
    assert result.success, result.message
    assert result.output.details == value
