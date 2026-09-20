from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from quadkit.web.cli.generators.controller import ControllerGenerator

PYPROJECT = '[project]\nname = "demo"\nversion = "0.1.0"\n'


def _render(tmp_path: Path, *layout: str, **kwargs: object) -> str:
    """Generate a controller inside an anchored src-layout project.

    Args:
        tmp_path: Scratch project root.
        *layout: Output directory parts below the project root.
        **kwargs: Forwarded to :meth:`ControllerGenerator.generate`.

    Returns:
        The rendered controller source.
    """
    (tmp_path / "pyproject.toml").write_text(PYPROJECT)
    out = tmp_path.joinpath(*layout)
    out.mkdir(parents=True, exist_ok=True)
    result = ControllerGenerator(output_dir=out).generate("Message", **kwargs)
    return Path(result.files_created[0]).read_text()


def test_controller_uses_resource_path():
    with tempfile.TemporaryDirectory() as tmp:
        gen = ControllerGenerator(output_dir=tmp)
        result = gen.generate("Message", path="/api/messages")
        file_path = result.files_created[0]
        content = Path(file_path).read_text()
        assert '@get("/api/messages")' in content
        assert '@get("/api/messages/{item_id}")' in content
        assert '@post("/api/messages", status_code=201)' in content
        assert '@put("/api/messages/{item_id}")' in content
        assert '@delete("/api/messages/{item_id}")' in content


def test_controller_delegates_to_repo():
    with tempfile.TemporaryDirectory() as tmp:
        gen = ControllerGenerator(output_dir=tmp)
        gen.generate("Message")
        content = Path(tmp, "message_controller.py").read_text()
        assert "self.repo.list(" in content
        assert "self.repo.get(" in content
        assert "self.repo.create(" in content
        assert "self.repo.update(" in content
        assert "self.repo.delete(" in content


def test_controller_no_double_suffix():
    with tempfile.TemporaryDirectory() as tmp:
        gen = ControllerGenerator(output_dir=tmp)
        result = gen.generate("MessageController")
        file_path = result.files_created[0]
        assert not str(file_path).endswith("_controller_controller.py")
        content = Path(file_path).read_text()
        assert "class MessageController(Controller)" in content
        assert "Service" not in content


# -- QK-1: sibling package imports follow the project structure ----------


def test_repository_import_is_bare_in_structured_layout(tmp_path: Path) -> None:
    """Structured layouts keep component packages directly under ``src``."""
    content = _render(tmp_path, "src", "controllers")
    assert "from repositories.message_repository import MessageRepository" in content
    assert "from domains.message import MessageCreate, MessageUpdate" in content


def test_repository_import_is_prefixed_in_minimal_layout(tmp_path: Path) -> None:
    """Minimal layouts nest component packages under the app package."""
    content = _render(tmp_path, "src", "app", "controllers")
    assert "from app.repositories.message_repository import MessageRepository" in content
    assert "from app.domains.message import MessageCreate, MessageUpdate" in content


def test_repository_import_is_prefixed_in_modular_layout(tmp_path: Path) -> None:
    """Modular layouts nest component packages under the feature module."""
    content = _render(tmp_path, "src", "app", "modules", "billing", "controllers")
    assert (
        "from app.modules.billing.repositories.message_repository import "
        "MessageRepository" in content
    )


def test_repository_import_falls_back_without_project_anchor(tmp_path: Path) -> None:
    """Outside a project the historical bare package name is preserved."""
    out = tmp_path / "out"
    out.mkdir(parents=True, exist_ok=True)
    result = ControllerGenerator(output_dir=out).generate("Message")
    content = Path(result.files_created[0]).read_text()
    assert "from repositories.message_repository import MessageRepository" in content


# -- QK-2: create/update validate through the generated DTOs -------------


def test_create_and_update_validate_payloads(tmp_path: Path) -> None:
    """Write handlers construct the Create/Update DTOs before hitting the repo."""
    content = _render(tmp_path, "src", "app", "controllers")
    assert "payload = MessageCreate(**data)" in content
    assert "payload = MessageUpdate(**data)" in content
    assert "from pydantic import ValidationError" in content
    # Partial patch semantics: only the supplied fields reach the repository.
    assert 'payload.model_dump(mode="json", exclude_unset=True)' in content


def test_read_only_controller_omits_validation_imports(tmp_path: Path) -> None:
    """A read-only controller must not import write-only symbols."""
    content = _render(tmp_path, "src", "app", "controllers", ops="list,get")
    assert "ValidationError" not in content
    assert "MessageCreate" not in content
    assert "@post(" not in content
    assert "@put(" not in content
    assert "@delete(" not in content


# -- QK-6: ops selection -------------------------------------------------


@pytest.mark.parametrize(
    ("ops", "expected", "absent"),
    [
        ("list", ["@get(\"/messages\")\n"], ["@post(", "@put(", "@delete("]),
        ("create", ["@post("], ["@get(", "@put(", "@delete("]),
        ("update", ["@put("], ["@get(", "@post(", "@delete("]),
        ("delete", ["@delete("], ["@get(", "@post(", "@put("]),
    ],
)
def test_ops_renders_only_requested_handlers(
    tmp_path: Path, ops: str, expected: list[str], absent: list[str]
) -> None:
    """Each operation maps to exactly its own route decorator."""
    content = _render(tmp_path, "src", "controllers", ops=ops)
    for fragment in expected:
        assert fragment in content
    for fragment in absent:
        assert fragment not in content


def test_ops_accepts_an_iterable(tmp_path: Path) -> None:
    """Callers may pass a sequence instead of a comma-separated string."""
    content = _render(tmp_path, "src", "controllers", ops=["create", "get"])
    assert "@post(" in content
    assert "@get(" in content
    assert "@put(" not in content
    assert "@delete(" not in content


def test_unknown_ops_are_rejected(tmp_path: Path) -> None:
    """A typo fails loudly instead of silently emitting an empty controller."""
    with pytest.raises(ValueError, match="Unknown controller ops"):
        _render(tmp_path, "src", "controllers", ops="list,bogus")


def test_every_ops_subset_parses_and_is_framed_consistently(tmp_path: Path) -> None:
    """Generated controllers stay syntactically valid for any operation set."""
    import ast

    for index, ops in enumerate(
        ("list", "get", "create", "update", "delete", "create,get,list")
    ):
        content = _render(tmp_path, "src", f"run{index}", "controllers", ops=ops)
        ast.parse(content)
        assert content.endswith("\n")
        assert not content.endswith("\n\n")
