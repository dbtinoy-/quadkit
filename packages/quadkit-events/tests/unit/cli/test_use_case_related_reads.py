"""Explicit related-row snapshots are not cross-entity transactions."""

import runpy
from pathlib import Path
from uuid import uuid4

import pytest
from quadkit.contracts.exceptions import (
    AuthorizationError,
    NotFoundError,
    PermissionDeniedError,
)
from quadkit.events.cli.generators.use_case import UseCaseGenerator
from quadkit.result import Err, Ok
from use_case_related_read_support import Repository, spec


@pytest.fixture
def generated(tmp_path):
    UseCaseGenerator(tmp_path).generate(
        "classify_post", fields_str="category_id:uuid", spec=spec()
    )
    return runpy.run_path(str(tmp_path / "classify_post_use_case.py"))


async def test_copy_related_snapshot_into_only_the_aggregate(generated):
    target, category = uuid4(), uuid4()
    aggregate = Repository(Ok({"category_title": "old"}))
    related_row = {"title": "News", "secret": "not projected"}
    related = Repository(Ok(related_row))
    result = await generated["ClassifyPostHandler"](
        aggregate, related_category_repository=related
    ).handle(
        generated["ClassifyPostCommand"](category_id=category).for_aggregate(target)
    )
    assert result.success
    assert related.reads == [str(category)]
    assert aggregate.updates == [(str(target), {"category_title": "News"})]
    assert related.updates == []
    assert related_row == {"title": "News", "secret": "not projected"}


@pytest.mark.parametrize(
    ("result", "code"),
    [
        (Err(NotFoundError("missing")), "related_not_found"),
        (Err(AuthorizationError("private denial")), "forbidden"),
        (Err(PermissionDeniedError("private denial")), "forbidden"),
        (Err(ValueError("database unavailable")), "related_repository_error"),
        (Ok(None), "invalid_related"),
        (Ok([]), "invalid_related"),
        (Ok({"other": "missing title"}), "invalid_related"),
    ],
)
async def test_related_read_failure_never_writes(generated, result, code):
    aggregate = Repository(Ok({"category_title": "old"}))
    related = Repository(result)
    outcome = await generated["ClassifyPostHandler"](
        aggregate, related_category_repository=related
    ).handle(
        generated["ClassifyPostCommand"](category_id=uuid4()).for_aggregate(uuid4())
    )
    assert not outcome.success
    assert outcome.code == code
    assert aggregate.updates == related.updates == []


@pytest.mark.parametrize("key", [None, "not-a-uuid", 1, True])
async def test_invalid_lookup_input_is_rejected_before_reads(generated, key):
    aggregate, related = Repository(Ok({})), Repository(Ok({"title": "News"}))
    outcome = await generated["ClassifyPostHandler"](
        aggregate, related_category_repository=related
    ).handle(generated["ClassifyPostCommand"](category_id=key).for_aggregate(uuid4()))
    assert not outcome.success
    assert aggregate.reads == related.reads == []


@pytest.mark.parametrize(
    "raw",
    [
        {},
        [None],
        [{"name": "category"}],
        [{"name": "category", "key": "input.missing", "fields": ["title"]}],
        [{"name": "category", "key": "aggregate.category_id", "fields": ["title"]}],
        [{"name": "category", "key": "input.category_id", "fields": []}],
        [
            {
                "name": "category",
                "key": "input.category_id",
                "fields": ["title", "title"],
            }
        ],
        [{"name": "category", "key": "input.category_id", "fields": ["_secret"]}],
        [
            {
                "name": "category",
                "key": "input.category_id",
                "fields": ["title"],
                "extra": True,
            }
        ],
        [{"name": "bad.name", "key": "input.category_id", "fields": ["title"]}],
    ],
)
@pytest.mark.parametrize("dry_run", [False, True])
def test_invalid_related_contract_fails_before_file_writes(
    tmp_path: Path, raw, dry_run
):
    config = spec() | {"related_reads": raw}
    with pytest.raises((ValueError, TypeError), match="related"):
        UseCaseGenerator(tmp_path).generate(
            "classify_post", fields_str="category_id:uuid", spec=config, dry_run=dry_run
        )
    assert not list(tmp_path.rglob("*.py"))


@pytest.mark.parametrize(
    "source",
    [
        "related.category.secret",
        "related.missing.title",
        "related.category.title.upper()",
    ],
)
def test_undeclared_related_projection_preserves_forced_file(tmp_path: Path, source):
    path = tmp_path / "classify_post_use_case.py"
    path.write_bytes(b"# user-owned\n")
    config = spec() | {"writes": [{"field": "title", "source": source}]}
    with pytest.raises(ValueError, match="related"):
        UseCaseGenerator(tmp_path).generate(
            "classify_post", fields_str="category_id:uuid", spec=config, force=True
        )
    assert path.read_bytes() == b"# user-owned\n"


@pytest.mark.parametrize(
    "fields_str", ["category_id:int", "category_id:bool", "category_id:uuid?"]
)
def test_related_keys_require_required_string_or_uuid(tmp_path, fields_str):
    with pytest.raises(ValueError, match="related key"):
        UseCaseGenerator(tmp_path).generate(
            "classify_post", fields_str=fields_str, spec=spec()
        )


def test_related_reads_require_input_validation(tmp_path):
    with pytest.raises(ValueError, match="related reads require validate_inputs"):
        UseCaseGenerator(tmp_path).generate(
            "classify_post",
            fields_str="category_id:uuid",
            spec=spec() | {"validate_inputs": False},
        )


def test_duplicate_related_names_are_rejected(tmp_path):
    config = spec()
    config["related_reads"] *= 2
    with pytest.raises(ValueError, match="related read names"):
        UseCaseGenerator(tmp_path).generate(
            "classify_post", fields_str="category_id:uuid", spec=config
        )


@pytest.mark.parametrize("lane", ["stages", "enqueues"])
def test_related_sources_are_not_silently_enabled_in_effects(tmp_path, lane):
    config = spec() | {
        lane: [
            {
                "event": "Copied",
                "task_class": "CopyTask",
                "payload": {"title": "related.category.title"},
            }
        ]
    }
    with pytest.raises(ValueError, match="related source"):
        UseCaseGenerator(tmp_path).generate(
            "classify_post", fields_str="category_id:uuid", spec=config
        )


@pytest.mark.parametrize("blocked", ["guard", "transition", "custom_steps"])
async def test_operation_refusal_happens_before_related_reads(tmp_path, blocked):
    from types import SimpleNamespace

    class Policy:
        async def evaluate(self, *_args):
            return SimpleNamespace(allowed=False)

    extra = {
        "guard": {"guard": True, "principal_required": True},
        "transition": {
            "transition": {"field": "status", "from": "draft", "to": "published"}
        },
        "custom_steps": {"custom_steps": ["not implemented"]},
    }[blocked]
    UseCaseGenerator(tmp_path).generate(
        "classify_post", fields_str="category_id:uuid", spec=spec() | extra
    )
    module = runpy.run_path(str(tmp_path / "classify_post_use_case.py"))
    aggregate, related = (
        Repository(Ok({"status": "published"})),
        Repository(Ok({"title": "News"})),
    )
    handler_args = {"policy": Policy()} if blocked == "guard" else {}
    command_args = (
        {"principal_sub": "actor", "principal": SimpleNamespace(user_id="actor")}
        if blocked == "guard"
        else {}
    )
    handler = module["ClassifyPostHandler"](
        aggregate, related_category_repository=related, **handler_args
    )
    command = module["ClassifyPostCommand"](
        category_id=uuid4(), **command_args
    ).for_aggregate(uuid4())
    if blocked == "custom_steps":
        with pytest.raises(NotImplementedError):
            await handler.handle(command)
    else:
        assert not (await handler.handle(command)).success
    assert related.reads == []
    assert aggregate.updates == []


async def test_all_related_reads_finish_before_any_mutation(tmp_path):
    config = spec()
    config["related_reads"].append(
        {"name": "editor", "key": "input.category_id", "fields": ["name"]}
    )
    config["writes"].append({"field": "editor_name", "source": "related.editor.name"})
    UseCaseGenerator(tmp_path).generate(
        "classify_post", fields_str="category_id:uuid", spec=config
    )
    module = runpy.run_path(str(tmp_path / "classify_post_use_case.py"))
    original = {"category_title": "old"}
    aggregate, related, editor = (
        Repository(Ok(original)),
        Repository(Ok({"title": "News"})),
        Repository(Err(NotFoundError("missing editor"))),
    )
    outcome = await module["ClassifyPostHandler"](
        aggregate, related_category_repository=related, related_editor_repository=editor
    ).handle(module["ClassifyPostCommand"](category_id=uuid4()).for_aggregate(uuid4()))
    assert not outcome.success
    assert original == {"category_title": "old"}
    assert aggregate.updates == related.updates == editor.updates == []


@pytest.mark.parametrize("typed", [False, True])
@pytest.mark.parametrize("key", ["category-1", ""])
async def test_string_keys_and_untyped_outcomes(tmp_path, typed, key):
    UseCaseGenerator(tmp_path).generate(
        "classify_post",
        fields_str="category_id:str",
        spec=spec() | {"typed_outcomes": typed},
    )
    module = runpy.run_path(str(tmp_path / "classify_post_use_case.py"))
    aggregate, related = Repository(Ok({})), Repository(Ok({"title": "News"}))
    result = await module["ClassifyPostHandler"](
        aggregate, related_category_repository=related
    ).handle(module["ClassifyPostCommand"](category_id=key).for_aggregate(uuid4()))
    assert result.success is bool(key)
    assert related.reads == ([key] if key else [])
