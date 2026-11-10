"""Standalone use-case output has a resolvable, honest repository contract."""

from __future__ import annotations

from datetime import date, datetime
import importlib.util
from pathlib import Path
import subprocess
import sys
from typing import get_type_hints
from uuid import uuid4

import pytest

from quadkit.events.cli.generators.use_case import UseCaseGenerator
from quadkit.result import Ok


def load_generated(path: Path, monkeypatch: pytest.MonkeyPatch):
    spec = importlib.util.spec_from_file_location("standalone_generated", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    ("fields", "options", "methods", "needs_datetime"),
    [
        (None, {}, {"get"}, False),
        ("day:date", {}, {"get"}, False),
        ("day:date", {"validate_inputs": True}, {"get"}, True),
        ("when:datetime", {}, {"get"}, True),
        (
            None,
            {"writes": [{"field": "updated_at", "source": "clock"}]},
            {"get", "update"},
            True,
        ),
        (
            None,
            {
                "atomic_transition": True,
                "transition": {"field": "status", "from": "draft", "to": "published"},
            },
            {"get_for_transition", "transition_if"},
            False,
        ),
    ],
)
def test_standalone_generated_annotations_and_imports(
    tmp_path, monkeypatch, fields, options, methods, needs_datetime
):
    UseCaseGenerator(tmp_path).generate("publish_post", fields_str=fields, spec=options)
    path = tmp_path / "publish_post_use_case.py"
    source = path.read_text()
    module = load_generated(path, monkeypatch)
    assert (
        get_type_hints(module.PublishPostHandler.__init__)["repository"]
        is module.RepositoryProtocol
    )
    assert get_type_hints(module.PublishPostCommand)
    for name in ("get", "get_for_transition", "update", "transition_if"):
        assert hasattr(module.RepositoryProtocol, name) == (name in methods)
    assert (
        "import datetime" in source or "datetime," in source or ", datetime" in source
    ) == needs_datetime

    ruff = Path(sys.executable).with_name("ruff")
    if not ruff.exists():
        pytest.skip("Ruff is required to check generated imports and references")
    lint = subprocess.run(
        [str(ruff), "check", "--select", "F", str(path)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert lint.returncode == 0, lint.stdout + lint.stderr


@pytest.mark.asyncio
async def test_default_repository_protocol_can_be_satisfied_by_caller(
    tmp_path, monkeypatch
):
    UseCaseGenerator(tmp_path).generate("publish_post")
    module = load_generated(tmp_path / "publish_post_use_case.py", monkeypatch)

    class Repository:
        async def get(self, key):
            return Ok({"id": key})

    result = await module.PublishPostHandler(Repository()).handle(
        module.PublishPostCommand().for_aggregate(uuid4())
    )
    assert result.success


@pytest.mark.asyncio
async def test_date_validation_still_rejects_datetime(tmp_path, monkeypatch):
    UseCaseGenerator(tmp_path).generate(
        "publish_post", fields_str="day:date", spec={"validate_inputs": True}
    )
    module = load_generated(tmp_path / "publish_post_use_case.py", monkeypatch)

    class Repository:
        async def get(self, key):
            return Ok({"id": key})

    handler = module.PublishPostHandler(Repository())
    target = uuid4()
    assert not (
        await handler.handle(
            module.PublishPostCommand(day=datetime(2026, 1, 1)).for_aggregate(target)
        )
    ).success
    assert (
        await handler.handle(
            module.PublishPostCommand(day=date(2026, 1, 1)).for_aggregate(target)
        )
    ).success


def test_supplied_repository_import_remains_authoritative(tmp_path, monkeypatch):
    (tmp_path / "custom_repository.py").write_text("class PostRepository: pass\n")
    monkeypatch.syspath_prepend(str(tmp_path))
    UseCaseGenerator(tmp_path).generate(
        "publish_post",
        spec={
            "repository": "PostRepository",
            "repository_import": "from custom_repository import PostRepository",
        },
    )
    path = tmp_path / "publish_post_use_case.py"
    module = load_generated(path, monkeypatch)
    assert "class RepositoryProtocol" not in path.read_text()
    assert (
        get_type_hints(module.PublishPostHandler.__init__)["repository"]
        is module.PostRepository
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("source", ["aggregate.title", "input.title"])
async def test_standalone_event_payload_still_uses_the_right_source(
    tmp_path, monkeypatch, source
):
    (tmp_path / "custom_events.py").write_text(
        "class Published:\n    def __init__(self, title): self.title = title\n"
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    UseCaseGenerator(tmp_path).generate(
        "publish_post",
        fields_str="title:str",
        spec={
            "stages": [
                {
                    "event": "Published",
                    "import": "from custom_events import Published",
                    "payload": {"title": source},
                }
            ],
        },
    )
    path = tmp_path / "publish_post_use_case.py"
    module = load_generated(path, monkeypatch)

    class Repository:
        async def get(self, key):
            return Ok({"id": key, "title": "stored"})

    class EventStore:
        def __init__(self):
            self.events = []

        async def append(self, *, stream_id, expected_version, events):
            self.events.extend(events)

    store = EventStore()
    result = await module.PublishPostHandler(Repository(), store).handle(
        module.PublishPostCommand(title="authored").for_aggregate(uuid4())
    )
    assert result.success
    assert store.events[0].title == (
        "stored" if source == "aggregate.title" else "authored"
    )
