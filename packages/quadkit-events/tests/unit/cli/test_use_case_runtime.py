"""Use-case templates must work against the generated SQL repository contract."""

from __future__ import annotations

from datetime import UTC, date, datetime, time
import importlib.util
import sys
from types import SimpleNamespace
from uuid import uuid4

import pytest

from quadkit.events.cli.generators.use_case import UseCaseGenerator
from quadkit.result import Err, Ok


@pytest.fixture
def generated(tmp_path, monkeypatch):
    UseCaseGenerator(tmp_path).generate(
        "publish_post",
        fields_str="title:str",
        spec={
            "transition": {"field": "status", "from": "draft", "to": "published"},
            "writes": [{"field": "title", "source": "input.title"}],
        },
    )
    spec = importlib.util.spec_from_file_location(
        "generated_publish_post", tmp_path / "publish_post_use_case.py"
    )
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    return module


class Repository:
    """The same Result/dict API the generated SQL repository exposes."""

    def __init__(self, row=None, *, update_error=False):
        self.row = row
        self.update_error = update_error
        self.updates = []
        self.reads = 0

    async def get(self, key):
        self.reads += 1
        assert isinstance(key, str)
        return Err(ValueError("not found")) if self.row is None else Ok(self.row)

    async def update(self, key, values):
        self.updates.append((key, values))
        if self.update_error:
            return Err(ValueError("conflict"))
        self.row = {**self.row, **values}
        return Ok(self.row)


@pytest.mark.asyncio
async def test_transition_and_input_write_use_repository_result_contract(generated):
    target = uuid4()
    repo = Repository({"id": str(target), "status": "draft", "title": "old"})
    handler = generated.PublishPostHandler(repo)
    result = await handler.handle(
        generated.PublishPostCommand(title="new").for_aggregate(target)
    )
    assert result.success
    assert repo.updates == [(str(target), {"status": "published", "title": "new"})]


@pytest.mark.asyncio
async def test_transition_guard_does_not_write(generated):
    repo = Repository({"status": "published", "title": "old"})
    result = await generated.PublishPostHandler(repo).handle(
        generated.PublishPostCommand(title="new").for_aggregate(uuid4())
    )
    assert not result.success
    assert "cannot move" in result.message
    assert repo.updates == []


@pytest.mark.asyncio
async def test_missing_and_conflicting_rows_return_failure(generated):
    command = generated.PublishPostCommand(title="new").for_aggregate(uuid4())
    missing = await generated.PublishPostHandler(Repository()).handle(command)
    conflicting = await generated.PublishPostHandler(
        Repository({"status": "draft"}, update_error=True)
    ).handle(command)
    assert not missing.success
    assert not conflicting.success
    assert "update failed" in conflicting.message


@pytest.mark.asyncio
async def test_missing_target_never_reads_or_writes(generated):
    repo = Repository({"status": "draft"})
    result = await generated.PublishPostHandler(repo).handle(
        generated.PublishPostCommand(title="new")
    )
    assert not result.success
    assert repo.updates == []


@pytest.fixture
def guarded(tmp_path, monkeypatch):
    UseCaseGenerator(tmp_path).generate(
        "publish_post",
        fields_str="title:str",
        spec={
            "principal_required": True,
            "guard": True,
            "transition": {"field": "status", "from": "draft", "to": "published"},
            "writes": [{"field": "title", "source": "input.title"}],
        },
    )
    spec = importlib.util.spec_from_file_location(
        "generated_guarded_publish", tmp_path / "publish_post_use_case.py"
    )
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    return module


class Policy:
    def __init__(self, allowed):
        self.allowed = allowed
        self.calls = []

    async def evaluate(self, principal, resource):
        self.calls.append((principal, dict(resource)))
        return SimpleNamespace(allowed=self.allowed)


@pytest.mark.asyncio
async def test_policy_denies_before_any_update(guarded):
    repo = Repository({"status": "draft", "title": "old"})
    policy = Policy(False)
    actor = SimpleNamespace(user_id="user-1")
    command = guarded.PublishPostCommand(
        title="new", principal_sub="user-1", principal=actor
    ).for_aggregate(uuid4())
    result = await guarded.PublishPostHandler(repo, policy).handle(command)
    assert not result.success
    assert "forbidden" in result.message
    assert not hasattr(result, "code")  # Standalone defaults stay unchanged.
    assert policy.calls == [(actor, {"status": "draft", "title": "old"})]
    assert repo.updates == []


@pytest.mark.asyncio
async def test_allowed_policy_executes_transition(guarded):
    repo = Repository({"status": "draft", "title": "old"})
    policy = Policy(True)
    command = guarded.PublishPostCommand(
        title="new", principal_sub="user-1", principal=SimpleNamespace(user_id="user-1")
    ).for_aggregate(uuid4())
    result = await guarded.PublishPostHandler(repo, policy).handle(command)
    assert result.success
    assert repo.row["status"] == "published"
    assert len(policy.calls) == 1


@pytest.mark.asyncio
async def test_absent_principal_cannot_reach_repository_or_policy(guarded):
    repo = Repository({"status": "draft", "title": "old"})
    policy = Policy(True)
    command = guarded.PublishPostCommand(title="new", principal_sub="user-1")
    result = await guarded.PublishPostHandler(repo, policy).handle(
        command.for_aggregate(uuid4())
    )
    assert not result.success
    assert "principal required" in result.message
    assert policy.calls == []
    assert repo.updates == []


def test_policy_requires_principal_contract(tmp_path):
    with pytest.raises(ValueError, match="requires an authenticated principal"):
        UseCaseGenerator(tmp_path).generate("publish_post", spec={"guard": True})


@pytest.mark.asyncio
async def test_subject_mismatch_cannot_write(guarded):
    repo = Repository({"status": "draft"})
    policy = Policy(True)
    command = guarded.PublishPostCommand(
        title="new",
        principal_sub="victim",
        principal=SimpleNamespace(user_id="attacker"),
    ).for_aggregate(uuid4())
    result = await guarded.PublishPostHandler(repo, policy).handle(command)
    assert not result.success
    assert policy.calls == []
    assert repo.updates == []


@pytest.mark.asyncio
async def test_non_boolean_allow_decision_fails_closed(guarded):
    repo = Repository({"status": "draft"})
    policy = Policy("yes")
    command = guarded.PublishPostCommand(
        title="new", principal_sub="user-1", principal=SimpleNamespace(user_id="user-1")
    ).for_aggregate(uuid4())
    result = await guarded.PublishPostHandler(repo, policy).handle(command)
    assert not result.success
    assert repo.updates == []


@pytest.mark.asyncio
async def test_custom_work_is_sanitized_and_stops_before_write(tmp_path, monkeypatch):
    UseCaseGenerator(tmp_path).generate(
        "publish_post",
        spec={
            "transition": {"field": "status", "from": "draft", "to": "published"},
            "custom_steps": ["Check rules\nraise RuntimeError('injected')"],
        },
    )
    path = tmp_path / "publish_post_use_case.py"
    assert "# @TODO: Check rules raise RuntimeError('injected')" in path.read_text()
    spec = importlib.util.spec_from_file_location("custom_publish", path)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    repo = Repository({"status": "draft"})
    command = module.PublishPostCommand().for_aggregate(uuid4())
    with pytest.raises(NotImplementedError, match="custom use-case work"):
        await module.PublishPostHandler(repo).handle(command)
    assert repo.row == {"status": "draft"}
    assert repo.updates == []


@pytest.mark.asyncio
async def test_transition_values_with_quotes_and_newlines_are_safe_python(
    tmp_path, monkeypatch
):
    source_value = 'old """ state\nline'
    target_value = 'new """ state\nline'
    UseCaseGenerator(tmp_path).generate(
        "publish_post",
        spec={
            "transition": {"field": "status", "from": source_value, "to": target_value}
        },
    )
    path = tmp_path / "publish_post_use_case.py"
    compile(path.read_text(), str(path), "exec")
    spec = importlib.util.spec_from_file_location("quoted_transition", path)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    command = module.PublishPostCommand().for_aggregate(uuid4())
    repo = Repository({"status": source_value})
    result = await module.PublishPostHandler(repo).handle(command)
    assert result.success
    assert repo.row["status"] == target_value
    denied = await module.PublishPostHandler(Repository({"status": "other"})).handle(
        command
    )
    assert not denied.success
    assert target_value in denied.message


@pytest.fixture
def checked(tmp_path, monkeypatch):
    UseCaseGenerator(tmp_path).generate(
        "publish_post",
        fields_str=(
            "title:str,count:int,amount:decimal,active:bool,moment:datetime,"
            "day:date,hour:time,key:uuid,payload:json,blob:bytes,maybe:str?"
        ),
        spec={
            "validate_inputs": True,
            "strict_json_inputs": True,
            "transition": {"field": "status", "from": "draft", "to": "published"},
            "writes": [
                {"field": "title", "source": "input.title"},
                {"field": "published_at", "source": "clock"},
            ],
        },
    )
    path = tmp_path / "publish_post_use_case.py"
    spec = importlib.util.spec_from_file_location("checked_publish", path)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    return module


def _valid_inputs():
    return {
        "title": "Title",
        "count": 1,
        "amount": 1.5,
        "active": True,
        "moment": datetime(2025, 1, 1, tzinfo=UTC),
        "day": date(2025, 1, 1),
        "hour": time(12),
        "key": uuid4(),
        "payload": {"nested": [1, "two"]},
        "blob": b"content",
        "maybe": None,
        "occurred_at": datetime(2025, 1, 1, tzinfo=UTC),
    }


@pytest.mark.parametrize(
    ("field", "invalid"),
    [
        ("title", None),
        ("count", True),  # bool is an int subclass, but not an integer input.
        ("amount", "1.5"),
        ("amount", float("nan")),
        ("amount", float("inf")),
        ("active", 1),
        ("moment", date(2025, 1, 1)),
        ("day", datetime(2025, 1, 1)),  # datetime is a date subclass.
        ("hour", "12:00"),
        ("key", "not-a-uuid"),
        ("payload", []),
        ("payload", {1: "non-string key"}),
        ("blob", "not bytes"),
        ("maybe", object()),
        ("occurred_at", "not a clock"),
    ],
)
@pytest.mark.asyncio
async def test_checked_inputs_reject_invalid_values_before_read(
    checked, field, invalid
):
    values = _valid_inputs()
    values[field] = invalid
    repo = Repository({"status": "draft"})
    result = await checked.PublishPostHandler(repo).handle(
        checked.PublishPostCommand(**values).for_aggregate(uuid4())
    )
    assert not result.success
    assert f"invalid input {field}" in result.message
    assert repo.reads == 0
    assert repo.updates == []


@pytest.mark.asyncio
async def test_checked_inputs_accept_valid_values_and_optional_none(checked):
    repo = Repository({"status": "draft"})
    values = _valid_inputs()
    result = await checked.PublishPostHandler(repo).handle(
        checked.PublishPostCommand(**values).for_aggregate(uuid4())
    )
    assert result.success
    assert repo.reads == 1
    assert repo.row["title"] == values["title"]
    assert repo.row["published_at"] == values["occurred_at"]


@pytest.mark.asyncio
async def test_checked_invalid_aggregate_id_fails_before_read(checked):
    repo = Repository({"status": "draft"})
    result = await checked.PublishPostHandler(repo).handle(
        checked.PublishPostCommand(**_valid_inputs()).for_aggregate("not-a-uuid")
    )
    assert not result.success
    assert "invalid aggregate id" in result.message
    assert repo.reads == 0


def test_checked_generator_rejects_unknown_types(tmp_path):
    with pytest.raises(ValueError, match="cannot be validated"):
        UseCaseGenerator(tmp_path).generate(
            "publish_post", fields_str="value:unknown", spec={"validate_inputs": True}
        )


@pytest.mark.asyncio
async def test_standalone_default_does_not_add_input_validation(generated):
    repo = Repository({"status": "draft"})
    result = await generated.PublishPostHandler(repo).handle(
        generated.PublishPostCommand(title=42).for_aggregate(uuid4())
    )
    assert result.success
    assert repo.row["title"] == 42


@pytest.fixture
def enum_checked(tmp_path, monkeypatch):
    special = 'special """\nchoice'
    UseCaseGenerator(tmp_path).generate(
        "publish_post",
        fields_str="choice:str?",
        spec={
            "validate_inputs": True,
            "enum_inputs": {"choice": ["draft", special]},
            "writes": [{"field": "status", "source": "input.choice"}],
        },
    )
    path = tmp_path / "publish_post_use_case.py"
    compile(path.read_text(), str(path), "exec")
    spec = importlib.util.spec_from_file_location("enum_checked_publish", path)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("choice", ["draft", 'special """\nchoice', None])
@pytest.mark.asyncio
async def test_checked_enum_accepts_options_and_optional_null(enum_checked, choice):
    repo = Repository({"status": "old"})
    command = enum_checked.PublishPostCommand(choice=choice).for_aggregate(uuid4())
    result = await enum_checked.PublishPostHandler(repo).handle(command)
    assert result.success
    assert repo.row["status"] == choice


@pytest.mark.asyncio
async def test_checked_enum_denies_other_values_before_read(enum_checked):
    repo = Repository({"status": "old"})
    command = enum_checked.PublishPostCommand(choice="unknown").for_aggregate(uuid4())
    result = await enum_checked.PublishPostHandler(repo).handle(command)
    assert not result.success
    assert "invalid enum input choice" in result.message
    assert repo.reads == 0
    assert repo.updates == []


@pytest.mark.parametrize(
    ("enum_inputs", "validation", "error"),
    [
        ({"choice": ["ok"]}, False, ValueError),
        ({"unknown": ["ok"]}, True, ValueError),
        ({"choice; print('x')": ["ok"]}, True, ValueError),
        ({"choice": []}, True, ValueError),
        ({"choice": [7]}, True, ValueError),
        ([], True, TypeError),
    ],
)
def test_enum_spec_fails_closed(tmp_path, enum_inputs, validation, error):
    with pytest.raises(error):
        UseCaseGenerator(tmp_path).generate(
            "publish_post",
            fields_str="choice:str",
            spec={"validate_inputs": validation, "enum_inputs": enum_inputs},
        )


@pytest.fixture
def numeric_checked(tmp_path, monkeypatch):
    UseCaseGenerator(tmp_path).generate(
        "set_amount",
        fields_str="amount:float?,count:int",
        spec={
            "validate_inputs": True,
            "numeric_inputs": {
                "amount": {"min": -2.5, "max": 5.5},
                "count": {"min": 1, "max": 4},
            },
            "writes": [
                {"field": "amount", "source": "input.amount"},
                {"field": "count", "source": "input.count"},
            ],
        },
    )
    path = tmp_path / "set_amount_use_case.py"
    spec = importlib.util.spec_from_file_location("numeric_checked", path)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    ("amount", "count"), [(-2.5, 1), (5.5, 4), (0.0, 2), (None, 1)]
)
@pytest.mark.asyncio
async def test_checked_numeric_accepts_inclusive_bounds_and_null(
    numeric_checked, amount, count
):
    repo = Repository({})
    command = numeric_checked.SetAmountCommand(
        amount=amount, count=count
    ).for_aggregate(uuid4())
    result = await numeric_checked.SetAmountHandler(repo).handle(command)
    assert result.success
    assert repo.row == {"amount": amount, "count": count}


@pytest.mark.parametrize(("amount", "count"), [(-2.6, 1), (5.6, 1), (0.0, 0), (0.0, 5)])
@pytest.mark.asyncio
async def test_checked_numeric_rejects_out_of_range_before_read(
    numeric_checked, amount, count
):
    repo = Repository({})
    command = numeric_checked.SetAmountCommand(
        amount=amount, count=count
    ).for_aggregate(uuid4())
    result = await numeric_checked.SetAmountHandler(repo).handle(command)
    assert not result.success
    assert "invalid numeric range input" in result.message
    assert repo.reads == 0
    assert repo.updates == []


@pytest.mark.parametrize("amount", [float("nan"), float("inf"), float("-inf")])
@pytest.mark.asyncio
async def test_checked_float_rejects_nonfinite_before_read(numeric_checked, amount):
    repo = Repository({})
    command = numeric_checked.SetAmountCommand(amount=amount, count=1).for_aggregate(
        uuid4()
    )
    result = await numeric_checked.SetAmountHandler(repo).handle(command)
    assert not result.success
    assert "invalid input amount" in result.message
    assert repo.reads == 0
    assert repo.updates == []


@pytest.mark.parametrize(
    ("numeric_inputs", "validation", "error"),
    [
        ({"count": {"min": 1}}, False, ValueError),
        ({"unknown": {"min": 1}}, True, ValueError),
        ({"count.__class__": {"min": 1}}, True, ValueError),
        ({"count": {}}, True, ValueError),
        ({"count": {"min": True}}, True, ValueError),
        ({"count": {"min": float("nan")}}, True, ValueError),
        ({"count": {"min": 10**1000}}, True, ValueError),
        ({"count": {"max": float("inf")}}, True, ValueError),
        ({"count": {"min": 2, "max": 1}}, True, ValueError),
        ({"count": {"min": 0.1, "max": 0.9}}, True, ValueError),
        ({"count": {"min": "0"}}, True, ValueError),
        ({"count": {"lower": 0}}, True, ValueError),
        ([], True, TypeError),
    ],
)
def test_numeric_spec_fails_closed(tmp_path, numeric_inputs, validation, error):
    with pytest.raises(error):
        UseCaseGenerator(tmp_path).generate(
            "set_amount",
            fields_str="count:int",
            spec={"validate_inputs": validation, "numeric_inputs": numeric_inputs},
        )


@pytest.fixture
def length_checked(tmp_path, monkeypatch):
    UseCaseGenerator(tmp_path).generate(
        "set_content",
        fields_str="title:str?,blob:bytes",
        spec={
            "validate_inputs": True,
            "length_inputs": {
                "title": {"min": 2, "max": 4},
                "blob": {"min": 1, "max": 2},
            },
            "writes": [
                {"field": "title", "source": "input.title"},
                {"field": "blob", "source": "input.blob"},
            ],
        },
    )
    path = tmp_path / "set_content_use_case.py"
    spec = importlib.util.spec_from_file_location("length_checked", path)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    ("title", "blob"), [("ab", b"x"), ("wxyz", b"xy"), ("👨‍👩", b"x"), (None, b"x")]
)
@pytest.mark.asyncio
async def test_checked_lengths_accept_bounds_and_optional_null(
    length_checked, title, blob
):
    repo = Repository({})
    command = length_checked.SetContentCommand(title=title, blob=blob).for_aggregate(
        uuid4()
    )
    result = await length_checked.SetContentHandler(repo).handle(command)
    assert result.success
    assert repo.row == {"title": title, "blob": blob}


@pytest.mark.parametrize(
    ("title", "blob"), [("a", b"x"), ("abcde", b"x"), ("ab", b""), ("ab", b"abc")]
)
@pytest.mark.asyncio
async def test_checked_lengths_reject_outside_bounds_before_read(
    length_checked, title, blob
):
    repo = Repository({})
    command = length_checked.SetContentCommand(title=title, blob=blob).for_aggregate(
        uuid4()
    )
    result = await length_checked.SetContentHandler(repo).handle(command)
    assert not result.success
    assert "invalid length input" in result.message
    assert repo.reads == 0
    assert repo.updates == []


@pytest.mark.parametrize(
    ("length_inputs", "validation", "error"),
    [
        ({"title": {"min": 1}}, False, ValueError),
        ({"missing": {"min": 1}}, True, ValueError),
        ({"title.__class__": {"min": 1}}, True, ValueError),
        ({"title": {}}, True, ValueError),
        ({"title": {"min": -1}}, True, ValueError),
        ({"title": {"min": True}}, True, ValueError),
        ({"title": {"min": 1.5}}, True, ValueError),
        ({"title": {"min": 3, "max": 2}}, True, ValueError),
        ({"title": {"lower": 0}}, True, ValueError),
        ([], True, TypeError),
    ],
)
def test_length_spec_fails_closed(tmp_path, length_inputs, validation, error):
    with pytest.raises(error):
        UseCaseGenerator(tmp_path).generate(
            "set_content",
            fields_str="title:str",
            spec={"validate_inputs": validation, "length_inputs": length_inputs},
        )


@pytest.mark.asyncio
async def test_length_zero_bound_is_enforced(tmp_path, monkeypatch):
    UseCaseGenerator(tmp_path).generate(
        "set_content",
        fields_str="title:str",
        spec={
            "validate_inputs": True,
            "length_inputs": {"title": {"min": 0, "max": 0}},
        },
    )
    path = tmp_path / "set_content_use_case.py"
    spec = importlib.util.spec_from_file_location("zero_length", path)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    target = uuid4()
    repo = Repository({})
    ok = await module.SetContentHandler(repo).handle(
        module.SetContentCommand(title="").for_aggregate(target)
    )
    bad = await module.SetContentHandler(repo).handle(
        module.SetContentCommand(title="x").for_aggregate(target)
    )
    assert ok.success
    assert not bad.success
    assert "invalid length input" in bad.message
    assert repo.reads == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("change", "typed"),
    [
        ({"title": 1}, True),
        ({"title": "x"}, True),
        ({"choice": "bad"}, True),
        ({"count": 0}, True),
        ({"count": 0}, False),
    ],
)
async def test_input_failures_have_structured_codes_only_when_opted_in(
    tmp_path, monkeypatch, change, typed
):
    UseCaseGenerator(tmp_path).generate(
        "change_post",
        fields_str="title:str,choice:str,count:int",
        spec={
            "typed_outcomes": typed,
            "validate_inputs": True,
            "length_inputs": {"title": {"min": 2}},
            "enum_inputs": {"choice": ["ready"]},
            "numeric_inputs": {"count": {"min": 1}},
            "writes": [{"field": "title", "source": "input.title"}],
        },
    )
    spec = importlib.util.spec_from_file_location(
        "typed_change_post", tmp_path / "change_post_use_case.py"
    )
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    values = {"title": "valid", "choice": "ready", "count": 1} | change
    repo = Repository({})
    result = await module.ChangePostHandler(repo).handle(
        module.ChangePostCommand(**values).for_aggregate(uuid4())
    )
    assert result.success is False
    if typed:
        assert result.code == "invalid_input"
    else:
        assert not hasattr(result, "code")
    assert repo.reads == 0
    assert repo.updates == []


@pytest.mark.parametrize(
    ("targets", "fields", "writes", "validate", "error"),
    [
        (
            "owner",
            "owner:uuid",
            [{"field": "owner", "source": "input.owner"}],
            True,
            TypeError,
        ),
        (
            ["owner"],
            "owner:uuid",
            [{"field": "owner", "source": "input.owner"}],
            False,
            ValueError,
        ),
        (
            ["unknown"],
            "owner:uuid",
            [{"field": "owner", "source": "input.owner"}],
            True,
            ValueError,
        ),
        (
            ["owner"],
            "owner:str",
            [{"field": "owner", "source": "input.owner"}],
            True,
            ValueError,
        ),
        (
            ["owner"],
            "owner:uuid",
            [{"field": "owner", "source": "clock"}],
            True,
            ValueError,
        ),
        (
            ["owner"],
            "owner:uuid",
            [{"field": "owner", "source": "input.owner"}] * 2,
            True,
            ValueError,
        ),
    ],
)
def test_uuid_storage_spec_rejects_unsafe_or_inconsistent_inputs(
    tmp_path, targets, fields, writes, validate, error
):
    with pytest.raises(error):
        UseCaseGenerator(tmp_path).generate(
            "assign_owner",
            fields_str=fields,
            spec={
                "validate_inputs": validate,
                "uuid_write_fields": targets,
                "writes": writes,
            },
        )


@pytest.mark.asyncio
async def test_standalone_uuid_write_is_unchanged_without_storage_opt_in(
    tmp_path, monkeypatch
):
    UseCaseGenerator(tmp_path).generate(
        "assign_owner",
        fields_str="owner:uuid",
        spec={"writes": [{"field": "owner", "source": "input.owner"}]},
    )
    spec = importlib.util.spec_from_file_location(
        "standalone_uuid_write", tmp_path / "assign_owner_use_case.py"
    )
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    repo = Repository({})
    owner = uuid4()
    result = await module.AssignOwnerHandler(repo).handle(
        module.AssignOwnerCommand(owner=owner).for_aggregate(uuid4())
    )
    assert result.success
    assert repo.updates[0][1]["owner"] is owner


@pytest.mark.asyncio
async def test_strict_nested_json_rejects_unserializable_values_before_read(checked):
    cycle = {}
    cycle["self"] = cycle
    too_deep = {}
    cursor = too_deep
    for _ in range(2000):
        child = {}
        cursor["next"] = child
        cursor = child
    invalid = [
        {"nested": [{1: "key"}]},
        {"nested": [float("nan")]},
        {"nested": [float("inf")]},
        {"nested": [object()]},
        {"nested": (1, 2)},
        {"nested": "\ud800"},
        {"\ud800": "bad key"},
        cycle,
        too_deep,
    ]
    for payload in invalid:
        repo = Repository({"status": "draft"})
        values = {**_valid_inputs(), "payload": payload}
        result = await checked.PublishPostHandler(repo).handle(
            checked.PublishPostCommand(**values).for_aggregate(uuid4())
        )
        assert not result.success
        assert "invalid input payload" in result.message
        assert repo.reads == 0
        assert repo.updates == []


@pytest.mark.asyncio
async def test_strict_nested_json_accepts_shared_and_valid_values(checked):
    shared = {"items": [True, None, 3, 1.5, "hello 🌏"]}
    values = {**_valid_inputs(), "payload": {"left": shared, "right": shared}}
    repo = Repository({"status": "draft"})
    result = await checked.PublishPostHandler(repo).handle(
        checked.PublishPostCommand(**values).for_aggregate(uuid4())
    )
    assert result.success
    assert repo.reads == 1


def test_strict_json_requires_opt_in_to_basic_validation(tmp_path):
    with pytest.raises(ValueError, match="requires validate_inputs"):
        UseCaseGenerator(tmp_path).generate(
            "publish_post", fields_str="payload:json", spec={"strict_json_inputs": True}
        )


def test_strict_json_does_not_change_standalone_default(tmp_path):
    UseCaseGenerator(tmp_path).generate("publish_post", fields_str="payload:json")
    source = (tmp_path / "publish_post_use_case.py").read_text()
    assert "_is_strict_json_object" not in source


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("failure", "expected"),
    [
        ("missing", "not_found"),
        ("read_error", "repository_error"),
        ("transition", "transition_rejected"),
        ("write", "write_failed"),
    ],
)
async def test_typed_outcomes_distinguish_repository_and_transition_failures(
    tmp_path, monkeypatch, failure, expected
):
    from quadkit.contracts.exceptions import NotFoundError

    UseCaseGenerator(tmp_path).generate(
        "publish_post",
        fields_str="title:str",
        spec={
            "validate_inputs": True,
            "typed_outcomes": True,
            "atomic_transition": True,
            "transition": {"field": "status", "from": "draft", "to": "published"},
            "writes": [{"field": "title", "source": "input.title"}],
        },
    )
    spec = importlib.util.spec_from_file_location(
        "typed_failure_publish", tmp_path / "publish_post_use_case.py"
    )
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)

    class Repo:
        def __init__(self):
            self.writes = 0

        async def get_for_transition(self, key):
            if failure == "missing":
                return Err(NotFoundError("missing"))
            if failure == "read_error":
                return Err(ValueError("unexpected"))
            return Ok({"status": "published" if failure == "transition" else "draft"})

        async def transition_if(self, key, field, expected, values):
            self.writes += 1
            return Err(ValueError("failed"))

    repo = Repo()
    result = await module.PublishPostHandler(repo).handle(
        module.PublishPostCommand(title="value").for_aggregate(uuid4())
    )
    assert not result.success
    assert result.code == expected
    assert repo.writes == (1 if failure == "write" else 0)


@pytest.mark.asyncio
async def test_injected_subject_length_is_enforced_before_read(tmp_path, monkeypatch):
    UseCaseGenerator(tmp_path).generate(
        "assign_owner",
        spec={
            "principal_required": True,
            "validate_inputs": True,
            "typed_outcomes": True,
            "length_inputs": {"principal_sub": {"max": 64}},
            "writes": [{"field": "owner", "source": "principal"}],
        },
    )
    spec = importlib.util.spec_from_file_location(
        "bounded_subject_handler", tmp_path / "assign_owner_use_case.py"
    )
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    target = uuid4()
    repo = Repository({"owner": "old"})
    invalid_subject = "é" * 65
    result = await module.AssignOwnerHandler(repo).handle(
        module.AssignOwnerCommand(
            principal_sub=invalid_subject,
            principal=SimpleNamespace(user_id=invalid_subject),
        ).for_aggregate(target)
    )
    assert not result.success
    assert result.code == "invalid_input"
    assert repo.reads == 0
    assert repo.updates == []
    value = "é" * 64
    result = await module.AssignOwnerHandler(repo).handle(
        module.AssignOwnerCommand(
            principal_sub=value, principal=SimpleNamespace(user_id=value)
        ).for_aggregate(target)
    )
    assert result.success
    assert repo.row["owner"] == value
    repo = Repository({"owner": "old"})
    mismatch = await module.AssignOwnerHandler(repo).handle(
        module.AssignOwnerCommand(
            principal_sub="alice", principal=SimpleNamespace(user_id="bob")
        ).for_aggregate(target)
    )
    assert not mismatch.success
    assert repo.reads == 0
    assert repo.updates == []


def test_injected_subject_length_requires_a_valid_principal_contract(tmp_path):
    gen = UseCaseGenerator(tmp_path)
    with pytest.raises(ValueError, match="requires validate_inputs"):
        gen.generate(
            "assign",
            spec={
                "principal_required": True,
                "length_inputs": {"principal_sub": {"max": 3}},
            },
        )
    with pytest.raises(ValueError, match="must name a text or bytes field"):
        gen.generate(
            "assign",
            spec={
                "validate_inputs": True,
                "length_inputs": {"principal_sub": {"max": 3}},
            },
        )
    with pytest.raises(ValueError, match="no non-empty subject"):
        gen.generate(
            "assign",
            spec={
                "principal_required": True,
                "validate_inputs": True,
                "length_inputs": {"principal_sub": {"max": 0}},
            },
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", ["abc\x00def", "\ud800", "\udfff"])  # noqa: PT014
async def test_storage_text_checks_reject_invalid_input_before_repository(
    tmp_path, monkeypatch, bad
):
    UseCaseGenerator(tmp_path).generate(
        "change_title",
        fields_str="title:str?",
        spec={
            "validate_inputs": True,
            "typed_outcomes": True,
            "storage_text_inputs": ["title"],
            "writes": [{"field": "title", "source": "input.title"}],
        },
    )
    spec = importlib.util.spec_from_file_location(
        "storage_text_test", tmp_path / "change_title_use_case.py"
    )
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    repo = Repository({"title": "old"})
    handler = module.ChangeTitleHandler(repo)
    result = await handler.handle(
        module.ChangeTitleCommand(title=bad).for_aggregate(uuid4())
    )
    assert not result.success
    assert result.code == "invalid_input"
    assert repo.reads == 0
    assert repo.updates == []
    for value in (None, "é😀", ""):
        result = await handler.handle(
            module.ChangeTitleCommand(title=value).for_aggregate(uuid4())
        )
        assert result.success


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", ["id\x00x", "\ud800"])
async def test_storage_text_checks_cover_injected_subject(tmp_path, monkeypatch, bad):
    UseCaseGenerator(tmp_path).generate(
        "assign_owner",
        spec={
            "principal_required": True,
            "validate_inputs": True,
            "typed_outcomes": True,
            "storage_text_inputs": ["principal_sub"],
            "writes": [{"field": "owner", "source": "principal"}],
        },
    )
    spec = importlib.util.spec_from_file_location(
        "storage_subject_test", tmp_path / "assign_owner_use_case.py"
    )
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    repo = Repository({"owner": "old"})
    command = module.AssignOwnerCommand(
        principal_sub=bad, principal=SimpleNamespace(user_id=bad)
    ).for_aggregate(uuid4())
    result = await module.AssignOwnerHandler(repo).handle(command)
    assert not result.success
    assert result.code == "invalid_input"
    assert repo.reads == 0
    assert repo.updates == []


def test_storage_text_option_fails_closed_on_bad_spec(tmp_path):
    generator = UseCaseGenerator(tmp_path)
    with pytest.raises(TypeError, match="must be a list"):
        generator.generate("assign", spec={"storage_text_inputs": "title"})
    with pytest.raises(ValueError, match="requires validate_inputs"):
        generator.generate(
            "assign", fields_str="title:str", spec={"storage_text_inputs": ["title"]}
        )
    for field in ("unknown", "count", "principal_sub"):
        with pytest.raises(ValueError, match="must name string fields"):
            generator.generate(
                "assign",
                fields_str="count:int",
                spec={"validate_inputs": True, "storage_text_inputs": [field]},
            )


@pytest.mark.asyncio
async def test_sql_json_option_checks_nested_keys_and_values_before_reads(
    tmp_path, monkeypatch
):
    UseCaseGenerator(tmp_path).generate(
        "change_json",
        fields_str="payload:json?,other:json?",
        spec={
            "validate_inputs": True,
            "strict_json_inputs": True,
            "typed_outcomes": True,
            "storage_json_inputs": ["payload"],
            "writes": [{"field": "data", "source": "input.payload"}],
        },
    )
    spec = importlib.util.spec_from_file_location(
        "storage_json_test", tmp_path / "change_json_use_case.py"
    )
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    for bad in (
        {"nested": ["a\x00b"]},
        {"nested": [{"key\x00": "x"}]},
        {"x": "\ud800"},
    ):
        repo = Repository({"data": {}})
        result = await module.ChangeJsonHandler(repo).handle(
            module.ChangeJsonCommand(payload=bad).for_aggregate(uuid4())
        )
        assert not result.success
        assert result.code == "invalid_input"
        assert repo.reads == 0
        assert repo.updates == []
    for good in (None, {}, {"nested": [{"🌏": "é😀"}]}):
        repo = Repository({"data": {}})
        result = await module.ChangeJsonHandler(repo).handle(
            module.ChangeJsonCommand(payload=good, other={"nul": "\x00"}).for_aggregate(
                uuid4()
            )
        )
        assert result.success
        assert repo.updates[0][1]["data"] == good


def test_storage_json_option_fails_closed_on_bad_spec(tmp_path):
    generator = UseCaseGenerator(tmp_path)
    with pytest.raises(TypeError, match="storage_json_inputs must be a list"):
        generator.generate("assign", spec={"storage_json_inputs": "payload"})
    with pytest.raises(ValueError, match="requires strict_json_inputs"):
        generator.generate(
            "assign",
            fields_str="payload:json",
            spec={"storage_json_inputs": ["payload"]},
        )
    for bad in ("missing", "title", None):
        with pytest.raises(ValueError, match="must name JSON fields"):
            generator.generate(
                "assign",
                fields_str="payload:json,title:str",
                spec={
                    "validate_inputs": True,
                    "strict_json_inputs": True,
                    "storage_json_inputs": [bad],
                },
            )


@pytest.mark.asyncio
async def test_opt_in_ascii_alphabet_checks_before_repository_reads(
    tmp_path, monkeypatch
):
    UseCaseGenerator(tmp_path).generate(
        "label",
        fields_str="value:str?",
        spec={
            "validate_inputs": True,
            "typed_outcomes": True,
            "alphabet_inputs": {"value": "012ABC_"},
            "length_inputs": {"value": {"min": 2, "max": 4}},
            "writes": [{"field": "value", "source": "input.value"}],
        },
    )
    spec = importlib.util.spec_from_file_location(
        "alphabet_label", tmp_path / "label_use_case.py"
    )
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    for value in ("a1", "A!", "AB\n", "éA", 123, "A"):
        repo = Repository({"value": "old"})
        result = await module.LabelHandler(repo).handle(
            module.LabelCommand(value=value).for_aggregate(uuid4())
        )
        assert not result.success
        assert result.code == "invalid_input"
        assert repo.reads == 0
        assert repo.updates == []
    for value in ("A1", None):
        repo = Repository({"value": "old"})
        result = await module.LabelHandler(repo).handle(
            module.LabelCommand(value=value).for_aggregate(uuid4())
        )
        assert result.success
        assert repo.row["value"] == value


@pytest.mark.parametrize(
    ("alphabet", "fields", "validation"),
    [
        ("A", "value:str", False),
        ("", "value:str", True),
        ("AA", "value:str", True),
        ("é", "value:str", True),
        ("A!", "value:str", True),
        ("abc", "value:int", True),
        ("abc", "different:str", True),
    ],
)
def test_alphabet_spec_rejects_unsupported_fields_and_alphabets(
    tmp_path, alphabet, fields, validation
):
    with pytest.raises(ValueError, match=r"alphabet_inputs|alphabet input"):
        UseCaseGenerator(tmp_path).generate(
            "label",
            fields_str=fields,
            spec={
                "validate_inputs": validation,
                "alphabet_inputs": {"value": alphabet},
            },
        )


@pytest.fixture
def sql_temporal(tmp_path, monkeypatch):
    UseCaseGenerator(tmp_path).generate(
        "schedule",
        fields_str="day:date?,moment:datetime?,hour:time?",
        spec={
            "validate_inputs": True,
            "typed_outcomes": True,
            "storage_temporal_inputs": {
                "day": "date",
                "moment": "datetime",
                "hour": "time",
                "occurred_at": "datetime",
            },
            "writes": [
                {"field": "day", "source": "input.day"},
                {"field": "moment", "source": "input.moment"},
                {"field": "hour", "source": "input.hour"},
                {"field": "updated", "source": "clock"},
            ],
        },
    )
    spec = importlib.util.spec_from_file_location(
        "sql_temporal", tmp_path / "schedule_use_case.py"
    )
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    return module


@pytest.mark.asyncio
async def test_sql_temporal_validation_blocks_ambiguous_and_infinite_values_before_reads(
    sql_temporal,
):
    from datetime import timedelta, timezone, tzinfo

    class BrokenZone(tzinfo):
        def utcoffset(self, dt):
            raise RuntimeError("bad timezone")

    class FloatingZone(tzinfo):
        def utcoffset(self, dt):
            return None

    class DerivedDate(date):
        pass

    class DerivedDateTime(datetime):
        pass

    class DerivedTime(time):
        pass

    valid = {
        "day": date(2025, 1, 1),
        "moment": datetime(2025, 1, 1, tzinfo=UTC),
        "hour": time(12),
        "occurred_at": datetime(2025, 1, 1, tzinfo=UTC),
    }
    invalid = [
        ("day", date.min),
        ("day", date.max),
        ("day", DerivedDate(2025, 1, 1)),
        ("moment", datetime(2025, 1, 1)),
        ("moment", DerivedDateTime(2025, 1, 1, tzinfo=UTC)),
        ("moment", datetime(2025, 1, 1, tzinfo=FloatingZone())),
        ("moment", datetime(2025, 1, 1, tzinfo=BrokenZone())),
        ("moment", datetime.min.replace(tzinfo=UTC)),
        ("moment", datetime.max.replace(tzinfo=UTC)),
        ("moment", datetime(1, 1, 1, tzinfo=timezone(timedelta(hours=1)))),
        ("moment", datetime(9999, 12, 31, 23, tzinfo=timezone(timedelta(hours=-2)))),
        ("occurred_at", datetime(2025, 1, 1)),
        ("occurred_at", None),
        ("occurred_at", "2025-01-01"),
        ("hour", DerivedTime(12)),
        ("hour", time(12, tzinfo=UTC)),
        ("hour", time(12, tzinfo=FloatingZone())),
    ]
    for name, value in invalid:
        repo = Repository({})
        command = sql_temporal.ScheduleCommand(**{**valid, name: value}).for_aggregate(
            uuid4()
        )
        result = await sql_temporal.ScheduleHandler(repo).handle(command)
        assert not result.success
        assert result.code == (
            "invalid_context" if name == "occurred_at" else "invalid_input"
        )
        assert repo.reads == 0
        assert repo.updates == []
    for moment in (
        datetime(2025, 1, 1, tzinfo=UTC),
        datetime(2025, 1, 1, tzinfo=timezone(timedelta(hours=8))),
    ):
        repo = Repository({})
        result = await sql_temporal.ScheduleHandler(repo).handle(
            sql_temporal.ScheduleCommand(
                **{**valid, "moment": moment, "day": None, "hour": None}
            ).for_aggregate(uuid4())
        )
        assert result.success
        assert repo.row["moment"] == moment
        assert repo.row["day"] is None
        assert repo.row["hour"] is None


@pytest.mark.parametrize(
    "raw",
    [
        ["day"],
        {"day": "time"},
        {"missing": "date"},
        {"day": "bad"},
        {"day": []},
        {"value": "date"},
    ],
)
def test_sql_temporal_options_require_matching_declared_fields(tmp_path, raw):
    with pytest.raises((ValueError, TypeError), match="storage_temporal_inputs"):
        UseCaseGenerator(tmp_path).generate(
            "schedule",
            fields_str="day:date,value:str",
            spec={"validate_inputs": True, "storage_temporal_inputs": raw},
        )


def test_sql_temporal_options_require_validation_and_are_opt_in(tmp_path):
    with pytest.raises(ValueError, match="requires validate_inputs"):
        UseCaseGenerator(tmp_path).generate(
            "schedule",
            fields_str="day:date",
            spec={"storage_temporal_inputs": {"day": "date"}},
        )
    UseCaseGenerator(tmp_path).generate(
        "schedule", fields_str="day:date", spec={"validate_inputs": True}
    )
    assert (
        "SQL temporal portability"
        not in (tmp_path / "schedule_use_case.py").read_text()
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("ack", [False, None, 0, 1, "yes", {}, True])
@pytest.mark.parametrize("typed_outcomes", [False, True])
async def test_atomic_transition_requires_literal_true_write_acknowledgement(
    tmp_path, monkeypatch, ack, typed_outcomes
):
    UseCaseGenerator(tmp_path).generate(
        "publish_post",
        spec={
            "atomic_transition": True,
            "typed_outcomes": typed_outcomes,
            "transition": {"field": "status", "from": "draft", "to": "published"},
        },
    )
    spec = importlib.util.spec_from_file_location(
        "atomic_ack_handler", tmp_path / "publish_post_use_case.py"
    )
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)

    class Repo:
        def __init__(self):
            self.calls = []

        async def get_for_transition(self, key):
            return Ok({"status": "draft"})

        async def transition_if(self, *args):
            self.calls.append(args)
            return Ok(ack)

    repo = Repo()
    outcome = await module.PublishPostHandler(repo).handle(
        module.PublishPostCommand().for_aggregate(uuid4())
    )
    assert outcome.success is (ack is True)
    assert len(repo.calls) == 1
    if ack is not True:
        assert "aggregate update failed" in outcome.message
        if typed_outcomes:
            assert outcome.code == "write_failed"


@pytest.mark.asyncio
async def test_unconfirmed_transition_never_runs_standalone_follow_up_effects(
    tmp_path, monkeypatch
):
    """No claim is made that standalone follow-up effects are transactional."""
    (tmp_path / "atomic_effects.py").write_text(
        "class Published:\n"
        "    def __init__(self, aggregate_id): self.aggregate_id = aggregate_id\n"
        "class JobRunner:\n    pass\n"
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    UseCaseGenerator(tmp_path).generate(
        "publish_post",
        spec={
            "atomic_transition": True,
            "typed_outcomes": True,
            "transition": {"field": "status", "from": "draft", "to": "published"},
            "stages": [
                {"event": "Published", "import": "from atomic_effects import Published"}
            ],
            "enqueues": [
                {
                    "task_class": "IndexJob",
                    "runner_class": "JobRunner",
                    "import": "from atomic_effects import JobRunner",
                }
            ],
        },
    )
    spec = importlib.util.spec_from_file_location(
        "atomic_effect_handler", tmp_path / "publish_post_use_case.py"
    )
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)

    class Repo:
        async def get_for_transition(self, key):
            return Ok({"status": "draft"})

        async def transition_if(self, *args):
            return Ok(False)

    class Store:
        async def append(self, **kwargs):
            pytest.fail("unconfirmed transition staged an event")

    class Runner:
        async def run(self, **kwargs):
            pytest.fail("unconfirmed transition enqueued a job")

    result = await module.PublishPostHandler(Repo(), Store(), Runner()).handle(
        module.PublishPostCommand().for_aggregate(uuid4())
    )
    assert not result.success
    assert result.code == "write_failed"
