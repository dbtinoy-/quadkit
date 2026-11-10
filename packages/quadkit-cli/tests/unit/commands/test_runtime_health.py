"""Explicit runtime health selection, lifecycle and canonical result contracts."""

from __future__ import annotations

import asyncio
from dataclasses import replace
import sys
from types import ModuleType
from unittest.mock import AsyncMock, Mock

import pytest
from typer.testing import CliRunner

from quadkit.app.base import Application, AppState
from quadkit.cli.commands.runtime_health import run_runtime_checks, select_checks
from quadkit.cli.commands.system import app as system_app
from quadkit.cli.contributors.runtime import ContributorRuntime
from quadkit.cli.registry.health import CheckStatus
from quadkit.contracts.cli.contributions import HealthCheckContribution
from quadkit.contracts.core import HealthCheckResult, HealthStatus

CHECK = HealthCheckContribution(
    "db", "Probe", "health_fixture:probe", "test", critical=True, timeout=0.1
)


@pytest.fixture
def module(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    fixture = ModuleType("health_fixture")
    application = Mock(spec=Application)
    application.state = AppState.CREATED
    fixture.app = application
    fixture.probe = AsyncMock(return_value=HealthCheckResult("db"))
    monkeypatch.setitem(sys.modules, "health_fixture", fixture)
    return fixture


@pytest.mark.parametrize("status", list(HealthStatus))
@pytest.mark.parametrize("critical", [False, True])
async def test_status_mapping_and_lifecycle(
    module: ModuleType, status: HealthStatus, critical: bool
) -> None:
    module.probe.return_value = HealthCheckResult(
        "db", status, error="secret password", message="secret password"
    )
    (result,) = await run_runtime_checks(
        "health_fixture:app", [replace(CHECK, critical=critical)]
    )
    expected = (
        CheckStatus.PASS
        if status is HealthStatus.HEALTHY
        else CheckStatus.FAIL
        if critical
        else CheckStatus.WARNING
    )
    assert result.status is expected
    assert "secret" not in repr(result)
    module.app.start.assert_awaited_once()
    module.probe.assert_awaited_once_with(module.app.container)
    module.app.stop.assert_awaited_once()


@pytest.mark.parametrize("result", [None, {"status": "ok"}, True])
async def test_malformed_result_fails_closed(
    module: ModuleType, result: object
) -> None:
    module.probe.return_value = result
    (row,) = await run_runtime_checks("health_fixture:app", [CHECK])
    assert row.status is CheckStatus.FAIL
    module.app.stop.assert_awaited_once()


async def test_probe_timeout_stops_application(module: ModuleType) -> None:
    async def blocked(_container: object) -> None:
        await asyncio.Event().wait()

    module.probe.side_effect = blocked
    (row,) = await run_runtime_checks(
        "health_fixture:app", [replace(CHECK, timeout=0.01)]
    )
    assert row.status is CheckStatus.FAIL
    module.app.stop.assert_awaited_once()


@pytest.mark.parametrize("stage", ["start", "probe"])
async def test_cancellation_propagates_after_cleanup(
    module: ModuleType, stage: str
) -> None:
    target = module.app.start if stage == "start" else module.probe
    target.side_effect = asyncio.CancelledError
    with pytest.raises(asyncio.CancelledError):
        await run_runtime_checks("health_fixture:app", [CHECK])
    module.app.stop.assert_awaited_once()


async def test_start_failure_attempts_cleanup_without_probing(
    module: ModuleType,
) -> None:
    module.app.start.side_effect = RuntimeError("private boot failure")
    with pytest.raises(RuntimeError):
        await run_runtime_checks("health_fixture:app", [CHECK])
    module.probe.assert_not_called()
    module.app.stop.assert_awaited_once()


async def test_shutdown_failure_cannot_be_success(module: ModuleType) -> None:
    module.app.stop.side_effect = RuntimeError("private shutdown failure")
    with pytest.raises(RuntimeError):
        await run_runtime_checks("health_fixture:app", [CHECK])


@pytest.mark.parametrize("state", [AppState.RUNNING, AppState.STOPPED])
async def test_already_owned_application_is_not_started_or_stopped(
    module: ModuleType, state: AppState
) -> None:
    module.app.state = state
    with pytest.raises(ValueError, match="CREATED"):
        await run_runtime_checks("health_fixture:app", [CHECK])
    module.app.start.assert_not_called()
    module.app.stop.assert_not_called()


@pytest.mark.parametrize("requested", [[], ["test:missing"], ["test:db", "test:db"]])
def test_bad_selection_is_rejected(requested: list[str]) -> None:
    with pytest.raises(ValueError, match=r"distinct|Unknown"):
        select_checks([CHECK], requested)


@pytest.mark.parametrize("timeout", [0, -1, float("nan"), float("inf"), True])
def test_invalid_check_timeout_is_rejected(timeout: float) -> None:
    with pytest.raises(ValueError, match="timeout"):
        select_checks([replace(CHECK, timeout=timeout)], ["test:db"])


def test_ambiguous_selected_contribution_is_rejected() -> None:
    with pytest.raises(ValueError, match="ambiguous"):
        select_checks([CHECK, CHECK], ["test:db"])


@pytest.mark.parametrize("strict", [False, True])
@pytest.mark.parametrize("critical", [False, True])
def test_command_runtime_exit_policy(
    module: ModuleType, monkeypatch: pytest.MonkeyPatch, strict: bool, critical: bool
) -> None:
    module.probe.return_value = HealthCheckResult("db", HealthStatus.UNHEALTHY)
    runtime = ContributorRuntime(_health_checks=[replace(CHECK, critical=critical)])
    monkeypatch.setattr(ContributorRuntime, "from_entry_points", lambda: runtime)
    monkeypatch.setattr("quadkit.cli.commands.system.Path.exists", lambda _self: True)
    arguments = ["health", "--app", "health_fixture:app", "--check", "test:db"]
    if strict:
        arguments.append("--strict")
    result = CliRunner().invoke(system_app, arguments)
    assert result.exit_code == (1 if critical or strict else 0), result.output
    assert "unhealthy" in result.output
    module.app.stop.assert_awaited_once()


def test_file_only_mode_never_imports_or_boots_an_application(
    module: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("quadkit.cli.commands.system.Path.exists", lambda _self: True)
    result = CliRunner().invoke(system_app, ["health"])
    assert result.exit_code == 0
    assert "Runtime health not run" in result.output
    module.app.start.assert_not_called()


@pytest.mark.parametrize(
    "arguments", [["--app", "health_fixture:app"], ["--check", "test:db"]]
)
def test_opt_in_requires_app_and_check(
    module: ModuleType, arguments: list[str]
) -> None:
    result = CliRunner().invoke(system_app, ["health", *arguments])
    assert result.exit_code == 2
    module.app.start.assert_not_called()


def test_real_application_is_started_and_stopped_by_command(
    module: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    application = Application(name="cli-health")
    module.app = application

    async def probe(container: object) -> HealthCheckResult:
        assert application.state is AppState.RUNNING
        assert container is application.container
        return HealthCheckResult("real-app")

    module.probe = probe
    runtime = ContributorRuntime(_health_checks=[CHECK])
    monkeypatch.setattr(ContributorRuntime, "from_entry_points", lambda: runtime)
    monkeypatch.setattr("quadkit.cli.commands.system.Path.exists", lambda _self: True)
    result = CliRunner().invoke(
        system_app, ["health", "--app", "health_fixture:app", "--check", "test:db"]
    )
    assert result.exit_code == 0, result.output
    assert "healthy" in result.output
    assert application.state is AppState.STOPPED


@pytest.mark.parametrize("stage", ["start", "stop"])
async def test_lifecycle_timeouts_cannot_hang_or_report_success(
    module: ModuleType, stage: str
) -> None:
    async def blocked() -> None:
        await asyncio.Event().wait()

    target = module.app.start if stage == "start" else module.app.stop
    target.side_effect = blocked
    with pytest.raises(TimeoutError):
        await run_runtime_checks("health_fixture:app", [CHECK], lifecycle_timeout=0.01)
    module.app.stop.assert_awaited_once()


@pytest.mark.parametrize(
    "target", ["bad", "health_fixture:missing", "health_fixture:probe"]
)
async def test_invalid_application_target_never_starts_or_stops(
    module: ModuleType, target: str
) -> None:
    with pytest.raises(
        (ValueError, AttributeError), match=r"target|missing|Application"
    ):
        await run_runtime_checks(target, [CHECK])
    module.app.start.assert_not_called()
    module.app.stop.assert_not_called()


def test_only_requested_checks_are_selected_in_requested_order() -> None:
    other = replace(CHECK, name="other", check_path="missing:probe")
    assert select_checks([other, CHECK], ["test:db"]) == [CHECK]
    assert select_checks([CHECK, other], ["test:other", "test:db"]) == [other, CHECK]


def test_unknown_selection_rejected_before_boot(
    module: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = ContributorRuntime(_health_checks=[CHECK])
    monkeypatch.setattr(ContributorRuntime, "from_entry_points", lambda: runtime)
    result = CliRunner().invoke(
        system_app,
        ["health", "--app", "health_fixture:app", "--check", "test:missing"],
    )
    assert result.exit_code == 2
    module.app.start.assert_not_called()


def test_strict_file_only_mode_cannot_claim_runtime_acceptance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("quadkit.cli.commands.system.Path.exists", lambda _self: True)
    result = CliRunner().invoke(system_app, ["health", "--strict"])
    assert result.exit_code == 1
    assert "Runtime health not run" in result.output


async def test_one_failed_check_does_not_hide_the_other_selected_results(
    module: ModuleType,
) -> None:
    module.probe.side_effect = [
        RuntimeError("private failure"),
        HealthCheckResult("db"),
    ]
    rows = await run_runtime_checks(
        "health_fixture:app", [CHECK, replace(CHECK, name="second")]
    )
    assert [row.status for row in rows] == [CheckStatus.FAIL, CheckStatus.PASS]
    assert [row.name for row in rows] == ["test:db", "test:second"]
    module.app.start.assert_awaited_once()
    module.app.stop.assert_awaited_once()


def test_real_root_command_route_supports_runtime_options(
    module: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    from quadkit.cli.runtime.main import app as cli_app

    runtime = ContributorRuntime(_health_checks=[CHECK])
    monkeypatch.setattr(ContributorRuntime, "from_entry_points", lambda: runtime)
    monkeypatch.setattr("quadkit.cli.commands.system.Path.exists", lambda _self: True)
    result = CliRunner().invoke(
        cli_app,
        ["system", "health", "--app", "health_fixture:app", "--check", "test:db"],
    )
    assert result.exit_code == 0, result.output
    assert "test:db: healthy" in result.output
    module.app.stop.assert_awaited_once()
