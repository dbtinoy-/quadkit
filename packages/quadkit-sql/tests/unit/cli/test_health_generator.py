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
    assert health.status.value == "unhealthy"
    assert health.details == {"implementation_required": True}


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


@pytest.mark.parametrize("critical", [False, True])
async def test_unimplemented_probe_cannot_report_a_healthy_dependency(
    tmp_path: Path, critical: bool
) -> None:
    """A placeholder must remain non-healthy even in a composite result."""
    from quadkit.contracts.core.health import (
        AggregateHealthResult,
        HealthCheckResult,
        HealthStatus,
    )

    result = HealthCheckGenerator(tmp_path).generate("orders", critical=critical)
    path = Path(result.files_created[0])
    namespace: dict[str, object] = {}
    exec(compile(path.read_text(), str(path), "exec"), namespace)  # noqa: S102
    factory = namespace["Orders"]
    assert callable(factory)
    check = factory()
    assert check.critical is critical
    health = await check.check()
    assert health.status is HealthStatus.UNHEALTHY
    assert not health.is_healthy()
    assert health.details == {"implementation_required": True}
    assert "not implemented" in health.error
    composite = AggregateHealthResult(
        components=[HealthCheckResult("framework", HealthStatus.HEALTHY), health]
    )
    assert not composite.is_healthy()
    assert "# @TODO:" in path.read_text()

    from quadkit.monitor.health.checker import HealthChecker

    checker = HealthChecker()
    assert not checker.has(check.name)
    checker.add(check.name, check.check)
    status, results = await checker.run_all_with_summary()
    assert status is HealthStatus.UNHEALTHY
    assert results[check.name].details == {"implementation_required": True}
