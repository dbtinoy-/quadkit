"""Business Meridian: a required use-case enqueue fails closed.

A ``required`` enqueue must not silently skip when its runner is unbound, a
queue rejection after the aggregate write must surface as a truthful partial
failure, and a payload key outside the declared ``params`` must be refused
before any output is written. These are the source-level guarantees behind
``supports_use_case_job_effect_v1``.
"""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path
import sys
from uuid import uuid4

import pytest

from quadkit.contracts.infra.tasks.exceptions import TaskQueueError
from quadkit.events.cli.generators.use_case import UseCaseGenerator
from quadkit.result import Ok


def _required_spec(**overrides: object) -> dict[str, object]:
    spec: dict[str, object] = {
        "repository": "FakeRepository",
        "repository_import": "from demo import FakeRepository",
        "typed_outcomes": True,
        "writes": [{"field": "status", "source": "input.status"}],
        "enqueues": [
            {
                "task_class": "PublishTask",
                "runner_class": "PublishRunner",
                "import": "from demo import PublishRunner",
                "required": True,
                "params": {"title": "str"},
                "payload": {"title": "input.title"},
            }
        ],
    }
    spec.update(overrides)
    return spec


def test_required_enqueue_fails_closed_and_translates_rejection(tmp_path: Path) -> None:
    UseCaseGenerator(tmp_path).generate(
        "publish_post", fields_str="title:str,status:str", spec=_required_spec()
    )
    source = (tmp_path / "publish_post_use_case.py").read_text()
    ast.parse(source)

    # A missing binding returns a failure instead of skipping the effect.
    assert 'code="runner_unavailable"' in source
    # A queue rejection after the committed write is a truthful partial failure.
    assert "except TaskQueueError:" in source
    assert 'code="enqueue_failed"' in source
    # The typed queue error must be importable for the handler to catch it.
    assert (
        "from quadkit.contracts.infra.tasks.exceptions import TaskQueueError" in source
    )


def test_required_enqueue_without_runner_class_is_refused(tmp_path: Path) -> None:
    spec = _required_spec()
    spec["enqueues"] = [
        {
            "task_class": "PublishTask",
            "required": True,
            "payload": {"title": "input.title"},
        }
    ]
    with pytest.raises(ValueError, match="required enqueue must declare runner_class"):
        UseCaseGenerator(tmp_path).generate(
            "publish_post", fields_str="title:str,status:str", spec=spec
        )
    assert not list(tmp_path.rglob("*.py"))


def test_payload_key_outside_declared_params_is_refused(tmp_path: Path) -> None:
    spec = _required_spec()
    spec["enqueues"] = [
        {
            "task_class": "PublishTask",
            "runner_class": "PublishRunner",
            "import": "from demo import PublishRunner",
            "required": True,
            "params": {"title": "str"},
            "payload": {"title": "input.title", "details": "input.details"},
        }
    ]
    with pytest.raises(ValueError, match="are not in the declared params"):
        UseCaseGenerator(tmp_path).generate(
            "publish_post", fields_str="title:str,status:str,details:str", spec=spec
        )
    assert not list(tmp_path.rglob("*.py"))


def test_optional_enqueue_keeps_the_skip_contract(tmp_path: Path) -> None:
    # Backward compatibility: an enqueue without ``required`` still renders the
    # original optional-runner skip, and pulls in no queue-error import.
    spec: dict[str, object] = {
        "enqueues": [
            {
                "task_class": "PublishTask",
                "runner_class": "PublishRunner",
                "import": "from demo import PublishRunner",
                "payload": {"title": "input.title"},
            }
        ]
    }
    UseCaseGenerator(tmp_path).generate(
        "publish_post", fields_str="title:str", spec=spec
    )
    source = (tmp_path / "publish_post_use_case.py").read_text()
    ast.parse(source)
    assert "is not None:" in source
    assert "TaskQueueError" not in source


def _runtime_spec() -> dict[str, object]:
    return {
        "typed_outcomes": True,
        "writes": [{"field": "title", "source": "input.title"}],
        "enqueues": [
            {
                "task_class": "IndexJob",
                "runner_class": "IndexRunner",
                "import": "from job_effect_helpers import IndexRunner",
                "required": True,
                "params": {"title": "str"},
                "payload": {"title": "input.title"},
            }
        ],
    }


def _generate_and_load(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    (tmp_path / "job_effect_helpers.py").write_text(
        "class IndexRunner:\n    async def run(self, **kwargs): ...\n"
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    UseCaseGenerator(tmp_path).generate(
        "publish_post", fields_str="title:str", spec=_runtime_spec()
    )
    spec = importlib.util.spec_from_file_location(
        "job_effect_publish_post", tmp_path / "publish_post_use_case.py"
    )
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    return module


class _Repo:
    """The generated SQL repository's Result/dict contract, minimal for a write."""

    def __init__(self) -> None:
        self.updates: list[tuple[str, dict[str, object]]] = []

    async def get(self, key: str):
        return Ok({"title": "old", "status": "draft"})

    async def update(self, key: str, values: dict[str, object]):
        self.updates.append((key, values))
        return Ok({"title": values["title"]})


@pytest.mark.asyncio
async def test_required_runner_missing_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _generate_and_load(tmp_path, monkeypatch)
    result = await module.PublishPostHandler(_Repo()).handle(
        module.PublishPostCommand(title="Hello").for_aggregate(uuid4())
    )
    assert not result.success
    assert result.code == "runner_unavailable"


@pytest.mark.asyncio
async def test_queue_rejection_after_write_is_partial_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _generate_and_load(tmp_path, monkeypatch)

    class Rejecting:
        async def run(self, **kwargs: object) -> str:
            raise TaskQueueError("queue full")

    result = await module.PublishPostHandler(_Repo(), Rejecting()).handle(
        module.PublishPostCommand(title="Hello").for_aggregate(uuid4())
    )
    assert not result.success
    assert result.code == "enqueue_failed"
