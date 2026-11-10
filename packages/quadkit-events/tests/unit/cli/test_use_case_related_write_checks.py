"""Related snapshots must satisfy explicit targets before aggregate mutation."""

import runpy
from pathlib import Path
from uuid import uuid4

import pytest
from quadkit.events.cli.generators.use_case import UseCaseGenerator
from quadkit.result import Ok
from use_case_related_read_support import Repository, spec


@pytest.mark.parametrize(
    ("kind", "value", "bounds"),
    [
        ("str", 1, {}),
        ("str", "\x00", {}),
        ("str", "\ud800", {}),
        ("str", "x", {"min_length": 2}),
        ("str", "long", {"max_length": 3}),
        ("str", "other", {"enum": ["News"]}),
        ("int", True, {}),
        ("int", 1.5, {}),
        ("int", 0, {"minimum": 1}),
        ("float", float("nan"), {}),
        ("float", float("inf"), {}),
        ("float", 3.5, {"maximum": 3}),
        ("bool", 1, {}),
        ("str", None, {}),
    ],
)
async def test_invalid_related_target_is_rejected_before_mutation(
    tmp_path: Path, kind, value, bounds
):
    config = spec() | {
        "related_write_checks": [
            {"field": "category_title", "type": kind, "nullable": False, **bounds}
        ]
    }
    UseCaseGenerator(tmp_path).generate(
        "classify_post", fields_str="category_id:uuid", spec=config
    )
    module = runpy.run_path(str(tmp_path / "classify_post_use_case.py"))
    original = {"category_title": "old"}
    aggregate, related = Repository(Ok(original)), Repository(Ok({"title": value}))
    result = await module["ClassifyPostHandler"](
        aggregate, related_category_repository=related
    ).handle(module["ClassifyPostCommand"](category_id=uuid4()).for_aggregate(uuid4()))
    assert not result.success
    assert result.code == "invalid_related_value"
    assert original == {"category_title": "old"}
    assert aggregate.updates == related.updates == []


@pytest.mark.parametrize(
    ("kind", "value", "extra"),
    [
        ("str", "News", {"min_length": 4, "max_length": 4, "enum": ["News"]}),
        ("str", "é", {"max_length": 1}),
        ("str", None, {"nullable": True}),
        ("int", 2, {"minimum": 2, "maximum": 2}),
        ("float", 2.5, {"minimum": 2.5, "maximum": 2.5}),
        ("bool", False, {}),
    ],
)
@pytest.mark.parametrize("typed", [False, True])
async def test_valid_scalar_checks_preserve_values(tmp_path, kind, value, extra, typed):
    config = spec() | {
        "typed_outcomes": typed,
        "related_write_checks": [
            {"field": "category_title", "type": kind, "nullable": False, **extra}
        ],
    }
    UseCaseGenerator(tmp_path).generate(
        "classify_post", fields_str="category_id:uuid", spec=config
    )
    module = runpy.run_path(str(tmp_path / "classify_post_use_case.py"))
    aggregate, related = Repository(Ok({})), Repository(Ok({"title": value}))
    result = await module["ClassifyPostHandler"](
        aggregate, related_category_repository=related
    ).handle(module["ClassifyPostCommand"](category_id=uuid4()).for_aggregate(uuid4()))
    assert result.success
    assert aggregate.updates[0][1] == {"category_title": value}


BASE = {"field": "category_title", "type": "str", "nullable": False}


@pytest.mark.parametrize(
    "checks",
    [
        None,
        {},
        [],
        [None],
        [{}],
        [BASE, BASE],
        [{**BASE, "field": "missing"}],
        [{**BASE, "type": "json"}],
        [{"field": "category_title", "type": "str"}],
        [{**BASE, "nullable": "false"}],
        [{**BASE, "pattern": "ignored?"}],
        [{**BASE, "min_length": True}],
        [{**BASE, "max_length": -1}],
        [{**BASE, "min_length": 5, "max_length": 2}],
        [{**BASE, "minimum": 0}],
        [{**BASE, "enum": []}],
        [{**BASE, "enum": [1]}],
        [{**BASE, "enum": ["\x00"]}],
        [{**BASE, "enum": ["\ud800"]}],
        [{**BASE, "type": "int", "enum": ["str"]}],
        [{**BASE, "type": "float", "minimum": float("nan")}],
        [{**BASE, "type": "float", "maximum": float("inf")}],
        [{**BASE, "type": "int", "minimum": 10**1000}],
        [{**BASE, "type": "int", "minimum": 0.2, "maximum": 0.8}],
        [{**BASE, "type": "int", "minimum": 2, "maximum": 1}],
    ],
)
@pytest.mark.parametrize("dry_run", [False, True])
def test_malformed_target_checks_preserve_forced_files(tmp_path, checks, dry_run):
    path = tmp_path / "classify_post_use_case.py"
    path.write_bytes(b"# user-owned\n")
    with pytest.raises(ValueError, match="related"):
        UseCaseGenerator(tmp_path).generate(
            "classify_post",
            fields_str="category_id:uuid",
            spec=spec() | {"related_write_checks": checks},
            dry_run=dry_run,
            force=True,
        )
    assert path.read_bytes() == b"# user-owned\n"


async def test_all_target_checks_precede_any_transition_or_write(tmp_path):
    config = spec() | {
        "transition": {"field": "status", "from": "draft", "to": "published"},
        "related_write_checks": [
            BASE,
            {**BASE, "field": "other_title", "max_length": 1},
        ],
    }
    config["writes"].append(
        {"field": "other_title", "source": "related.category.title"}
    )
    UseCaseGenerator(tmp_path).generate(
        "classify_post", fields_str="category_id:uuid", spec=config
    )
    module = runpy.run_path(str(tmp_path / "classify_post_use_case.py"))
    original = {"status": "draft", "category_title": "old"}
    aggregate, related = Repository(Ok(original)), Repository(Ok({"title": "News"}))
    result = await module["ClassifyPostHandler"](
        aggregate, related_category_repository=related
    ).handle(module["ClassifyPostCommand"](category_id=uuid4()).for_aggregate(uuid4()))
    assert result.code == "invalid_related_value"
    assert original == {"status": "draft", "category_title": "old"}
    assert aggregate.updates == []


def test_related_write_check_capability_is_explicit():
    assert UseCaseGenerator.supports_related_write_checks_v1 is True
