"""Tests for contracts.cli.generators — project anchor discovery."""

from __future__ import annotations

from pathlib import Path

from quadkit.contracts.cli.generators import find_project_anchor

#: A workspace root declares membership without ever shipping a project.
WORKSPACE_ROOT = (
    "# Virtual workspace root - no [project] table.\n\n[tool.uv.workspace]\n"
)

PROJECT_TABLE = '[project]\nname = "demo"\nversion = "0.0.1"\n'


def test_comment_mentioning_project_is_not_an_anchor(tmp_path: Path) -> None:
    outer = tmp_path / "outer"
    inner = outer / "inner"
    inner.mkdir(parents=True)
    (outer / "pyproject.toml").write_text(PROJECT_TABLE, encoding="utf-8")
    (inner / "pyproject.toml").write_text(WORKSPACE_ROOT, encoding="utf-8")

    assert find_project_anchor(inner) == outer


def test_real_project_table_is_an_anchor(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(PROJECT_TABLE, encoding="utf-8")

    assert find_project_anchor(tmp_path) == tmp_path


def test_nearest_project_up_the_tree_wins(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(PROJECT_TABLE, encoding="utf-8")
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "pyproject.toml").write_text(PROJECT_TABLE, encoding="utf-8")

    assert find_project_anchor(nested) == nested
