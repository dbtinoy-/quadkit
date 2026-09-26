"""Packaging-metadata boundary tests for quadkit-monitor dependencies."""

from __future__ import annotations

from pathlib import Path
import tomllib


def _load_pyproject(path: Path) -> dict:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def test_quadkit_tasks_not_in_runtime_dependencies() -> None:
    """Runtime dependencies must not include quadkit-tasks."""
    pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
    data = _load_pyproject(pyproject)
    runtime_deps = data.get("project", {}).get("dependencies", [])

    assert not any(str(pkg).startswith("quadkit-tasks") for pkg in runtime_deps)


def test_quadkit_tasks_in_test_dependency_groups() -> None:
    """Test-only dependency declared in both test spots, like quadkit-testing."""
    pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
    data = _load_pyproject(pyproject)

    group = data.get("dependency-groups", {}).get("test", [])
    optional_test = (
        data.get("project", {}).get("optional-dependencies", {}).get("test", [])
    )

    assert any(str(pkg).startswith("quadkit-tasks") for pkg in group)
    assert any(str(pkg).startswith("quadkit-tasks") for pkg in optional_test)
