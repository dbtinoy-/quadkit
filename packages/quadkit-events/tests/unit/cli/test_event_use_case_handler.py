"""Native generated adapter delegates to the existing use case and real buses."""

import importlib
import sys
from uuid import uuid4

import pytest

from quadkit.events.buses.command import CommandBusImpl
from quadkit.events.buses.event import EventBusImpl
from quadkit.events.cli.generators.event_generator import EventGenerator
from quadkit.events.cli.generators.event_handler import EventHandlerGenerator
from quadkit.events.cli.generators.use_case import UseCaseGenerator
from quadkit.events.config import EventBusConfig
from quadkit.result import Ok

BINDING = {
    "module": "rename_post_use_case",
    "command": "RenamePostCommand",
    "result": "RenamePostResult",
    "event_module": "rename_requested_event",
    "event_class": "RenameRequestedEvent",
    "inputs": ["title"],
}


@pytest.fixture
def generated(tmp_path, monkeypatch):
    EventGenerator(tmp_path).generate("rename_requested", fields_str="title:str")
    UseCaseGenerator(tmp_path).generate(
        "rename_post",
        fields_str="title:str",
        spec={
            "validate_inputs": True,
            "typed_outcomes": True,
            "writes": [{"field": "title", "source": "input.title"}],
        },
    )
    EventHandlerGenerator(tmp_path).generate(
        "rename_from_event", event="rename_requested", use_case=BINDING
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    for name in [
        "rename_requested_event",
        "rename_post_use_case",
        "rename_from_event_handler",
    ]:
        monkeypatch.delitem(sys.modules, name, raising=False)
    modules = [
        importlib.import_module(name)
        for name in [
            "rename_requested_event",
            "rename_post_use_case",
            "rename_from_event_handler",
        ]
    ]
    yield modules
    for module in modules:
        sys.modules.pop(module.__name__, None)


class Repository:
    def __init__(self):
        self.row = {"title": "Old"}
        self.reads = 0
        self.updates = []

    async def get(self, key):
        self.reads += 1
        return Ok(dict(self.row))

    async def update(self, key, values):
        self.updates.append((key, values))
        self.row.update(values)
        return Ok(dict(self.row))


@pytest.mark.asyncio
async def test_real_event_and_command_buses_invoke_same_handler(generated):
    event_module, use_case, adapter = generated
    repository = Repository()
    commands = CommandBusImpl()
    commands.register(
        use_case.RenamePostCommand, use_case.RenamePostHandler(repository=repository)
    )
    handler = adapter.RenameFromEventHandler(commands)
    events = EventBusImpl(config=EventBusConfig(retry_failed_handlers=False))
    events.subscribe(event_module.RenameRequestedEvent, handler.on_rename_requested)
    key = uuid4()
    try:
        assert (
            await events.publish(
                event_module.build_rename_requested_event(aggregate_id=key, title="New")
            )
        ).is_ok()
        await events.flush()
        assert repository.updates == [(str(key), {"title": "New"})]
        assert not events.dispatch_errors
    finally:
        await events.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case", ["no_target", "string_target", "bad_input", "bus_failure", "wrong_result"]
)
async def test_invalid_context_input_and_dispatch_do_not_report_success(
    generated, case
):
    event_module, use_case, adapter = generated
    repository = Repository()
    commands = CommandBusImpl()
    commands.register(
        use_case.RenamePostCommand, use_case.RenamePostHandler(repository=repository)
    )
    if case in {"bus_failure", "wrong_result"}:

        class FailedBus:
            async def dispatch(self, command):
                if case == "bus_failure":
                    raise OSError("private transport detail")
                return object()

        commands = FailedBus()
    handler = adapter.RenameFromEventHandler(commands)
    target = (
        None
        if case == "no_target"
        else str(uuid4())
        if case == "string_target"
        else uuid4()
    )
    event = event_module.build_rename_requested_event(
        aggregate_id=target, title=42 if case == "bad_input" else "New"
    )
    with pytest.raises((ValueError, RuntimeError, OSError)):
        await handler.on_rename_requested(event)
    assert repository.updates == []
    assert repository.reads == 0


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("module", "app;run()"),
        ("command", "class"),
        ("event_class", "_Private"),
        ("inputs", ["principal_sub"]),
        ("inputs", ["metadata"]),
        ("inputs", ["title", "title"]),
        ("inputs", ["input.title"]),
        ("inputs", "title"),
        ("unexpected", True),
    ],
)
def test_bad_binding_refused_before_writes(tmp_path, field, value):
    with pytest.raises(ValueError, match="use_case"):
        EventHandlerGenerator(tmp_path).generate(
            "rename_from_event", use_case={**BINDING, field: value}
        )
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("principal", [False, True])
def test_runtime_binding_refuses_undeclared_command_context(generated, principal):
    from dataclasses import make_dataclass

    _, _, adapter = generated
    base = adapter.RenamePostCommand
    extra = "principal_sub" if principal else "undeclared_input"
    adapter.RenamePostCommand = make_dataclass(
        "ChangedCommand", [(extra, str)], bases=(base,), frozen=True, kw_only=True
    )
    with pytest.raises(ValueError, match="no implicit context"):
        adapter.RenameFromEventHandler(CommandBusImpl())


@pytest.mark.asyncio
async def test_bus_records_failed_use_case_instead_of_success(generated):
    event_module, use_case, adapter = generated
    repository = Repository()
    commands = CommandBusImpl()
    commands.register(
        use_case.RenamePostCommand, use_case.RenamePostHandler(repository=repository)
    )
    events = EventBusImpl(config=EventBusConfig(retry_failed_handlers=False))
    events.subscribe(
        event_module.RenameRequestedEvent,
        adapter.RenameFromEventHandler(commands).on_rename_requested,
    )
    try:
        assert (
            await events.publish(
                event_module.build_rename_requested_event(
                    aggregate_id=uuid4(), title=42
                )
            )
        ).is_ok()
        await events.flush()
        assert events.dispatch_errors
        assert repository.reads == 0
        assert repository.updates == []
    finally:
        await events.close()
