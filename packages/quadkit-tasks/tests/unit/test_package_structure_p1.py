"""P1 structural invariants for quadkit-tasks package layout.

These tests enforce the post-normalization directory structure.
They must fail before the refactor and pass after it.
"""

from __future__ import annotations

from pathlib import Path

# Root of the package source tree
_SRC = Path(__file__).parents[2] / "src" / "quadkit" / "tasks"


def test_middleware_directory_exists() -> None:
    """src/quadkit/tasks/middleware must exist after normalization."""
    assert (_SRC / "middleware").is_dir(), (
        "Expected src/quadkit/tasks/middleware/ to exist — "
        "middleware_pipeline/ should have been renamed to middleware/"
    )


def test_middleware_pipeline_directory_removed() -> None:
    """src/quadkit/tasks/middleware_pipeline must not exist after normalization."""
    assert not (_SRC / "middleware_pipeline").exists(), (
        "src/quadkit/tasks/middleware_pipeline/ still exists — "
        "it should have been removed and replaced by middleware/"
    )


def test_decorators_module_exists() -> None:
    """src/quadkit/tasks/decorators.py must exist after normalization."""
    assert (_SRC / "decorators.py").is_file(), (
        "Expected src/quadkit/tasks/decorators.py to exist — "
        "decorators/decorators.py should have been flattened to decorators.py"
    )


def test_decorators_directory_removed() -> None:
    """src/quadkit/tasks/decorators/ must not exist after normalization."""
    assert not (_SRC / "decorators").is_dir(), (
        "src/quadkit/tasks/decorators/ still exists — "
        "it should have been removed and replaced by decorators.py"
    )
