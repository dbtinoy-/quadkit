"""Use-case source tokens name declared data, never Python expressions."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from quadkit.events.cli.generators.use_case import UseCaseGenerator
from quadkit.serialization import dumps_str


def _source_spec(location: str, source: str) -> dict[str, object]:
    if location == "writes":
        return {"writes": [{"field": "title", "source": source}]}
    if location == "stages":
        return {"stages": [{"event": "Published", "payload": {"title": source}}]}
    return {"enqueues": [{"task_class": "PublishTask", "payload": {"title": source}}]}


@pytest.mark.parametrize("location", ["writes", "stages", "enqueues"])
@pytest.mark.parametrize("dry_run", [False, True])
@pytest.mark.parametrize(
    "source",
    [
        "input.missing",
        "input.id",
        "input.principal_sub",
        "input.occurred_at",
        "input.title.upper()",
        "input.title.__class__",
        "input.title\n",
        "input.\U0001d635\U0001d62a\U0001d635\U0001d62d\U0001d626",
        "input.class",
        "input.1value",
        "input.title or command.id",
        "input.",
    ],
)
def test_input_sources_reject_expressions_and_undeclared_members(
    tmp_path: Path, location: str, dry_run: bool, source: str
) -> None:
    # Injected context exists on the command but is not an authored input.
    spec = _source_spec(location, source) | {
        "principal_required": True,
        "writes": [{"field": "updated_at", "source": "clock"}],
    }
    if location == "writes":
        spec["writes"] = [
            {"field": "updated_at", "source": "clock"},
            {"field": "title", "source": source},
        ]
    with pytest.raises(ValueError, match="input source"):
        UseCaseGenerator(tmp_path).generate(
            "publish_post", fields_str="title:str", spec=spec, dry_run=dry_run
        )
    assert not list(tmp_path.rglob("*.py"))


@pytest.mark.parametrize("as_json", [False, True])
def test_invalid_source_preserves_existing_output_with_force(
    tmp_path: Path, as_json: bool
) -> None:
    path = tmp_path / "publish_post_use_case.py"
    original = "# application-owned file\n"
    path.write_text(original)
    spec = _source_spec("writes", "input.title.upper()")
    with pytest.raises(ValueError, match="input source"):
        UseCaseGenerator(tmp_path).generate(
            "publish_post",
            fields_str="title:str",
            spec=dumps_str(spec) if as_json else spec,
            force=True,
        )
    assert path.read_text() == original


@pytest.mark.parametrize("location", ["writes", "stages", "enqueues"])
@pytest.mark.parametrize("as_json", [False, True])
def test_declared_input_sources_render_valid_python(
    tmp_path: Path, location: str, as_json: bool
) -> None:
    spec = _source_spec(location, "input.title")
    generator = UseCaseGenerator(tmp_path)
    generator.generate(
        "publish_post",
        fields_str="title:str",
        spec=dumps_str(spec) if as_json else spec,
    )
    path = tmp_path / "publish_post_use_case.py"
    tree = ast.parse(path.read_text())
    assert any(
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "command"
        and node.attr == "title"
        for node in ast.walk(tree)
    )


@pytest.mark.parametrize("location", ["writes", "stages", "enqueues"])
@pytest.mark.parametrize("dry_run", [False, True])
@pytest.mark.parametrize("fields_str", [None, "principal_sub:str"])
def test_principal_sources_require_authenticated_context(
    tmp_path: Path, location: str, dry_run: bool, fields_str: str | None
) -> None:
    # A similarly named authored field must not substitute for trusted context.
    with pytest.raises(
        ValueError, match="principal source requires principal_required"
    ):
        UseCaseGenerator(tmp_path).generate(
            "publish_post",
            fields_str=fields_str,
            spec=_source_spec(location, "principal"),
            dry_run=dry_run,
        )
    assert not list(tmp_path.rglob("*.py"))


@pytest.mark.parametrize("location", ["writes", "stages", "enqueues"])
@pytest.mark.parametrize("as_json", [False, True])
def test_invalid_principal_source_preserves_forced_output(
    tmp_path: Path, location: str, as_json: bool
) -> None:
    path = tmp_path / "publish_post_use_case.py"
    original = b"# application-owned output\n"
    path.write_bytes(original)
    spec = _source_spec(location, "principal") | {"principal_required": False}
    with pytest.raises(
        ValueError, match="principal source requires principal_required"
    ):
        UseCaseGenerator(tmp_path).generate(
            "publish_post", spec=dumps_str(spec) if as_json else spec, force=True
        )
    assert path.read_bytes() == original


@pytest.mark.parametrize("location", ["writes", "stages", "enqueues"])
def test_authenticated_principal_source_still_renders(
    tmp_path: Path, location: str
) -> None:
    UseCaseGenerator(tmp_path).generate(
        "publish_post",
        spec=_source_spec(location, "principal") | {"principal_required": True},
    )
    tree = ast.parse((tmp_path / "publish_post_use_case.py").read_text())
    assert any(
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "command"
        and node.attr == "principal_sub"
        for node in ast.walk(tree)
    )
