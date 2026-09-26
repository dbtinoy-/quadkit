"""Guard generator: one variant's imports, and only that variant's usage.

`QUADKIT_FRAMEWORK_BUGS.md` AUTH-1: the template imported `RoleGuard` *and*
`PermissionGuard` unconditionally while rendering one of them, so every
generated guard carried an unused import (F401). The usage example at the
bottom had the same problem one step further out: a permission guard's file
advertised `...RoleGuard("admin")`, so a reader copying the example got a
NameError.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import sys

import pytest

from quadkit.auth.cli.generators.guard import AuthGuardGenerator

PYPROJECT = '[project]\nname = "demo"\nversion = "0.1.0"\n'


def _generate(tmp_path: Path, guard_type: str) -> Path:
    """Generate a guard inside an anchored src-layout project."""
    (tmp_path / "pyproject.toml").write_text(PYPROJECT)
    out = tmp_path / "src" / "guards"
    out.mkdir(parents=True, exist_ok=True)
    result = AuthGuardGenerator(output_dir=out).generate(
        "admin_only", type=guard_type, force=True
    )
    return Path(result.files_created[0])


@pytest.mark.parametrize(
    ("guard_type", "present", "absent"),
    [
        ("role", "RoleGuard", "PermissionGuard"),
        ("permission", "PermissionGuard", "RoleGuard"),
    ],
)
def test_only_the_rendered_variant_is_imported_or_mentioned(
    tmp_path: Path, guard_type: str, present: str, absent: str
) -> None:
    content = _generate(tmp_path, guard_type).read_text()

    assert present in content
    assert absent not in content, (
        f"the {guard_type} variant mentions {absent}: an unused import is the "
        "original defect, and a commented example naming the other variant is "
        "the same mistake in a comment"
    )


@pytest.mark.parametrize("guard_type", ["role", "permission"])
def test_the_generated_guard_is_lint_clean_and_importable(
    tmp_path: Path, guard_type: str
) -> None:
    path = _generate(tmp_path, guard_type)

    # ``--isolated`` from the generated project directory: that is how the
    # file is linted in the project it lands in.
    check = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "--isolated", str(path)],
        capture_output=True,
        text=True,
        check=False,
        cwd=tmp_path,
    )
    assert check.returncode == 0, check.stdout

    spec = importlib.util.spec_from_file_location(f"guard_{guard_type}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    assert hasattr(module, "AdminOnlyGuard")
