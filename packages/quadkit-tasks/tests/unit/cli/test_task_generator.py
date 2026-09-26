"""Task generator rendering tests."""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path
import subprocess
import sys

import pytest

from quadkit.tasks.cli.generators.task import TaskGenerator

PYPROJECT = '[project]\nname = "demo"\nversion = "0.1.0"\n'


def _render(tmp_path: Path, name: str, **kwargs: object) -> str:
    """Generate a task module inside an anchored src-layout project."""
    (tmp_path / "pyproject.toml").write_text(PYPROJECT)
    out = tmp_path / "src" / "tasks"
    out.mkdir(parents=True, exist_ok=True)
    result = TaskGenerator(output_dir=out).generate(name, **kwargs)
    return Path(result.files_created[0]).read_text()


def test_task_generator_uses_snake_case_function_name(tmp_path: Path) -> None:
    """Generated task entrypoints should be valid snake_case identifiers."""
    content = _render(tmp_path, "SendWeeklyDigest", schedule="0 9 * * 1")

    assert "async def send_weekly_digest(" in content
    assert "async def SendWeeklyDigest(" not in content
    assert 'name="send_weekly_digest"' in content


def test_task_generator_omits_dead_param_extraction(tmp_path: Path) -> None:
    """Generated task modules should not emit unused kwargs assignments."""
    content = _render(tmp_path, "cleanup", params_str="id=None,email=None")

    assert 'kwargs.get("id", None)' not in content
    assert 'kwargs.get("email", None)' not in content
    assert "result_data = await _process_cleanup(*args, **kwargs)" in content


def test_task_generator_output_is_syntactically_clean(tmp_path: Path) -> None:
    """Generated task modules should stay parseable and neatly framed."""
    content = _render(tmp_path, "cleanup", schedule="*/15 * * * *")

    ast.parse(content)
    assert content.endswith("\n")
    assert "@scheduled(\n" in content
    assert "\n\nasync def _process_cleanup(" in content


def test_task_runner_has_self_and_uses_local_job_id_factory(tmp_path: Path) -> None:
    """The generated enqueue helper must be a valid instance method."""
    content = _render(tmp_path, "cleanup")

    assert "async def run(\n        self," in content
    assert "id=uuid4().hex" in content
    assert "_uuid.uuid4" not in content


def _generate(tmp_path: Path, name: str, **kwargs: object) -> Path:
    """Generate a task module inside an anchored src-layout project."""
    (tmp_path / "pyproject.toml").write_text(PYPROJECT)
    out = tmp_path / "src" / "tasks"
    out.mkdir(parents=True, exist_ok=True)
    result = TaskGenerator(output_dir=out).generate(name, **kwargs)
    return Path(result.files_created[0])


def test_typed_params_render_annotations_and_defaults(tmp_path: Path) -> None:
    """``name:type=default`` is the declared shape, so it has to work.

    It did not: the parser split only on ``=``, so ``batch_size:int=100`` kept
    the type inside the *name* and rendered ``batch_size:int: Any = 100,`` —
    seven ``invalid-syntax`` errors on a file ``quadkit gen task`` had just
    written (tracker TASK-6).
    """
    path = _generate(
        tmp_path,
        "cleanup_sessions",
        params_str="batch_size:int=100,name:str=hello,limit:int,dry_run:bool",
    )
    content = path.read_text()

    assert "batch_size: int = 100," in content
    assert 'name: str = "hello",' in content
    assert "limit: int | None = None," in content
    assert "dry_run: bool | None = None," in content
    ast.parse(content)


def test_the_pre_type_spelling_still_parses_as_untyped(tmp_path: Path) -> None:
    """``name=default`` predates the type token and stays accepted."""
    content = _render(tmp_path, "cleanup", params_str="id=None,email=None")

    assert "id: Any = None," in content
    assert "email: Any = None," in content


def test_an_expression_default_survives_quoting(tmp_path: Path) -> None:
    """Only bare words are values; ``{}`` and calls stay as written."""
    content = _render(tmp_path, "cleanup", params_str="opts:json={},at:datetime=now()")

    assert "opts: dict[str, Any] = {}," in content
    assert "at: datetime = now()," in content


@pytest.mark.parametrize(
    "kwargs",
    [
        {},
        {"schedule": "*/15 * * * *"},
        {"params_str": "batch_size:int=100,limit:int"},
    ],
)
def test_generated_modules_are_lint_clean_and_importable(
    tmp_path: Path, kwargs: dict[str, object]
) -> None:
    """The acceptance TASK-3 asked for: clean out of the box, under defaults.

    ``--isolated`` is how a generated project lints — it ships no ruff config
    of its own for these rules — and ``cwd`` is the generated project rather
    than wherever the test happens to run: ruff's default first-party
    detection depends on the working directory, and linting from inside the
    framework's own ``packages/quadkit-tasks`` makes ``quadkit.tasks`` look
    first-party. That is a property of this repository, not of the file.
    """
    path = _generate(tmp_path, "cleanup", **kwargs)

    check = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "--isolated", str(path)],
        capture_output=True,
        text=True,
        check=False,
        cwd=tmp_path,
    )
    assert check.returncode == 0, check.stdout
    formatted = subprocess.run(
        [sys.executable, "-m", "ruff", "format", "--check", "--isolated", str(path)],
        capture_output=True,
        text=True,
        check=False,
        cwd=tmp_path,
    )
    assert formatted.returncode == 0, formatted.stdout

    spec = importlib.util.spec_from_file_location(f"gen_{path.stem}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    assert hasattr(module, "cleanup")
