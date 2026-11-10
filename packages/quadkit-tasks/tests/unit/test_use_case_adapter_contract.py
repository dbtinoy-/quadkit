"""Characterize native worker boundaries before admitting use-case adapters.

These are runtime probes, not a generated binding or SQL application proof.
Returned domain failures are data to the generic worker; adapters must translate
failure explicitly rather than assuming worker completion means command success.
"""

from __future__ import annotations

from dataclasses import dataclass
import importlib.util
from pathlib import Path
import sys
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.contracts import CommandBusProtocol
from quadkit.contracts.infra.tasks import JobStatus
from quadkit.di import Container
from quadkit.result import Err
from quadkit.tasks import MemoryTaskQueue, TaskProvider
from quadkit.tasks.cli.generators.task import TaskGenerator
from quadkit.tasks.exceptions import QueueFullError
from quadkit.tasks.execution.worker import TaskWorker, TaskWorkerServices
from quadkit.tasks.middleware.core import TaskMiddlewarePipeline
from quadkit.tasks.models.job import JobProtocol, JobResult


@dataclass
class _DomainOutcome:
    success: bool = False


class _Bus:
    """Only the dependency-resolution seam is under test here."""

    def __init__(self) -> None:
        self.calls: list[object] = []

    async def dispatch(self, command: object) -> str:
        self.calls.append(command)
        return "dispatched"


async def _dispatch_probe(
    payload: dict[str, object], command_bus: CommandBusProtocol
) -> object:
    return await command_bus.dispatch(payload)


@pytest.mark.parametrize("default_middleware", [True, False])
@pytest.mark.parametrize("kind", ["err", "outcome", "error_dict", "job_result"])
async def test_returned_failure_is_data_not_failed_execution(
    kind: str, default_middleware: bool
) -> None:
    """Do not wire command dispatch directly as a task and infer success."""
    value: object = {
        "err": Err(ValueError("domain rejected")),
        "outcome": _DomainOutcome(),
        "error_dict": {"status": "error"},
        "job_result": JobResult.fail("domain rejected"),
    }[kind]

    async def handler() -> object:
        return value

    worker = TaskWorker(
        "audit",
        MemoryTaskQueue(),  # type: ignore[abstract]  # Existing queue protocol typing debt.
        {"probe": handler},
        middleware_pipeline=None if default_middleware else TaskMiddlewarePipeline(),
    )
    job = JobProtocol(id="probe", name="probe")
    result = await worker._execute_job(job)
    assert result.is_ok()
    assert job.status == JobStatus.COMPLETED
    assert result.unwrap().success is True
    assert result.unwrap().data is value


async def test_missing_command_bus_fails_without_dispatch() -> None:
    """Native worker does not invent a command bus without its container."""
    dlq = MagicMock()
    worker = TaskWorker(
        "audit",
        MemoryTaskQueue(),  # type: ignore[abstract]  # Existing queue protocol typing debt.
        {"probe": _dispatch_probe},
        services=TaskWorkerServices(dead_letter_queue=dlq),
    )
    job = JobProtocol(id="probe", name="probe", kwargs={"payload": {"title": "New"}})
    result = await worker._execute_job(job)
    assert result.is_err()
    assert job.status == JobStatus.FAILED
    dlq.add.assert_called_once()


@pytest.mark.parametrize("provided_bus", [False, True])
async def test_command_bus_resolution_and_job_kwarg_precedence(
    provided_bus: bool,
) -> None:
    """DI is fallback for missing arguments, not a protected injection slot."""
    configured, supplied = _Bus(), _Bus()
    container = Container()
    container.singleton(CommandBusProtocol, configured, validate=False)
    kwargs: dict[str, Any] = {"payload": {"title": "New"}}
    if provided_bus:
        kwargs["command_bus"] = supplied
    worker = TaskWorker(
        "audit",
        MemoryTaskQueue(),  # type: ignore[abstract]  # Existing queue protocol typing debt.
        {"probe": _dispatch_probe},
        services=TaskWorkerServices(container=container),
    )
    job = JobProtocol(id="probe", name="probe", kwargs=kwargs)
    result = await worker._execute_job(job)
    assert result.is_ok()
    assert result.unwrap().data == "dispatched"
    assert configured.calls == ([] if provided_bus else [{"title": "New"}])
    assert supplied.calls == ([{"title": "New"}] if provided_bus else [])


async def test_retry_count_is_not_a_retry_policy() -> None:
    """Do not promise retries from JobConfig/JobProtocol.max_retries alone."""
    calls = 0

    async def handler() -> None:
        nonlocal calls
        calls += 1
        raise ValueError("rejected")

    dlq = MagicMock()
    worker = TaskWorker(
        "audit",
        MemoryTaskQueue(),  # type: ignore[abstract]  # Existing queue protocol typing debt.
        {"probe": handler},
        services=TaskWorkerServices(dead_letter_queue=dlq),
    )
    job = JobProtocol(id="probe", name="probe", max_retries=9)
    assert (await worker._execute_job(job)).is_err()
    assert calls == 1
    assert job.status == JobStatus.FAILED
    dlq.add.assert_called_once()


def test_current_task_generator_is_not_a_use_case_binding(tmp_path: Path) -> None:
    """A successful scaffold emission is not evidence of business execution."""
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname="audit"\nversion="0.1.0"\n'
    )
    generator = TaskGenerator(tmp_path / "src/tasks")
    assert not getattr(generator, "supports_use_case_binding_v1", False)
    generated = generator.generate("rename_post")
    source = Path(generated.files_created[0]).read_text()
    assert "# @TODO: Implement your task logic here." in source
    assert "CommandBusProtocol" not in source


@pytest.mark.parametrize("internal", [False, True])
async def test_enqueue_rejection_is_not_an_acknowledged_job(internal: bool) -> None:
    """Both producer and scheduler paths preserve a queue Err as failure."""
    error = QueueFullError("queue capacity reached")
    queue = MagicMock()
    queue.enqueue = AsyncMock(return_value=Err(error))
    provider = TaskProvider(queue, enable_scheduler=False)
    job = JobProtocol(id="rejected", name="probe")
    enqueue = provider._enqueue_job if internal else provider.enqueue_job
    with pytest.raises(QueueFullError) as caught:
        await enqueue(job)
    assert caught.value is error
    queue.enqueue.assert_awaited_once_with(job)


async def test_enqueue_infrastructure_error_propagates() -> None:
    """Do not turn broker connectivity failure into an accepted job ID."""
    error = ConnectionError("broker unavailable")
    queue = MagicMock()
    queue.enqueue = AsyncMock(side_effect=error)
    provider = TaskProvider(queue, enable_scheduler=False)
    with pytest.raises(ConnectionError) as caught:
        await provider.enqueue_job(JobProtocol(id="lost", name="probe"))
    assert caught.value is error


@pytest.mark.parametrize("rejected", [False, True])
async def test_generated_runner_reports_queue_acceptance(
    tmp_path: Path, rejected: bool
) -> None:
    """Exercise the unchanged native runner template, not a replacement runner."""
    from quadkit.result import Ok
    from quadkit.tasks.decorators import _clear_registered_tasks

    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname="audit"\nversion="0.1.0"\n'
    )
    generated = TaskGenerator(tmp_path / "src/tasks").generate(
        "rename_post", params_str="title:str"
    )
    module_name = "task_enqueue_contract_audit"
    assert module_name not in sys.modules
    spec = importlib.util.spec_from_file_location(
        module_name, generated.files_created[0]
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    queue = MagicMock()
    error = QueueFullError("queue capacity reached")
    queue.enqueue = AsyncMock(
        side_effect=lambda job: Err(error) if rejected else Ok(job.id)
    )
    try:
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        runner = module.RenamePostTaskRunner(
            TaskProvider(queue, enable_scheduler=False)
        )
        if rejected:
            with pytest.raises(QueueFullError) as caught:
                await runner.run(title="New")
            assert caught.value is error
        else:
            identifier = await runner.run(title="New")
            assert identifier == queue.enqueue.call_args.args[0].id
        queue.enqueue.assert_awaited_once()
        assert queue.enqueue.call_args.args[0].kwargs == {"title": "New"}
    finally:
        _clear_registered_tasks((module_name,))
        sys.modules.pop(module_name, None)
