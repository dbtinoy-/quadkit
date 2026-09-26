"""Health-check generator regression tests."""

from __future__ import annotations

import ast
from pathlib import Path
import subprocess
import sys

import pytest

from quadkit.sql.cli.generators.health_check import HealthCheckGenerator


@pytest.mark.asyncio
async def test_generated_health_check_returns_canonical_result(tmp_path: Path) -> None:
    """Generated checks must use HealthCheckResult's component/error fields."""
    result = HealthCheckGenerator(tmp_path).generate("DiskSpace")
    path = Path(result.files_created[0])
    content = path.read_text()
    ast.parse(content)

    namespace: dict[str, object] = {}
    exec(compile(content, str(path), "exec"), namespace)  # noqa: S102
    check = namespace["DiskSpace"]()
    health = await check.check()  # type: ignore[union-attr]

    assert health.component == "disk_space"
    assert health.status.value == "healthy"
    assert health.details == {}


@pytest.mark.parametrize(
    ("given", "expected_class", "expected_name"),
    [
        ("DiskSpace", "DiskSpace", "disk_space"),
        ("orders", "Orders", "orders"),
        ("payment_gateway", "PaymentGateway", "payment_gateway"),
    ],
)
async def test_the_check_class_is_pascal_case_whatever_the_input(
    tmp_path: Path, given: str, expected_class: str, expected_name: str
) -> None:
    """A snake_case entity must not become a snake_case *class* (HEALTH-1).

    The generator takes the name from a canvas node, where snake_case is the
    convention, and rendered it straight into the class declaration:
    ``class orders(HealthCheck)`` — PEP 8's N801, and nothing in ruff's
    default rule set flags it, so it reached the generated project silently.
    """
    result = HealthCheckGenerator(tmp_path).generate(given)
    content = Path(result.files_created[0]).read_text()

    assert f"class {expected_class}(HealthCheck):" in content
    assert f'name="{expected_name}"' in content

    namespace: dict[str, object] = {}
    exec(compile(content, str(result.files_created[0]), "exec"), namespace)  # noqa: S102
    check = namespace[expected_class]()  # type: ignore[operator]
    health = await check.check()  # type: ignore[union-attr]
    assert health.component == expected_name


def test_the_generated_module_is_lint_clean(tmp_path: Path) -> None:
    """``ruff check --isolated`` from the generated project directory."""
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "demo"\n')
    result = HealthCheckGenerator(tmp_path / "src" / "health").generate("orders")
    path = Path(result.files_created[0])

    check = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "--isolated", str(path)],
        capture_output=True,
        text=True,
        check=False,
        cwd=tmp_path,
    )
    assert check.returncode == 0, check.stdout
