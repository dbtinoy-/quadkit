"""Signed native webhook delegates only declared inputs to the command bus."""

from dataclasses import dataclass, field
import hashlib
import hmac
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace
from uuid import uuid4

import pytest

from quadkit import serialization as json
from quadkit.web.cli.generators.webhook import WebhookGenerator

SECRET = "test-only-server-owned-webhook-secret-32-bytes"
BINDING = {
    "module": "bound_operation",
    "command": "RenameCommand",
    "result": "RenameResult",
    "event_type": "rename_post",
    "inputs": ["title"],
}


@dataclass(frozen=True, kw_only=True)
class BaseCommand:
    id: object = field(default_factory=uuid4)
    timestamp: object = None
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True, kw_only=True)
class RenameCommand(BaseCommand):
    title: str

    def for_aggregate(self, target):
        return self, target


@dataclass(frozen=True)
class RenameResult:
    success: bool
    message: str = ""


@pytest.fixture
def generated(tmp_path, monkeypatch):
    monkeypatch.setitem(
        sys.modules,
        "bound_operation",
        SimpleNamespace(RenameCommand=RenameCommand, RenameResult=RenameResult),
    )
    WebhookGenerator(tmp_path).generate("rename", use_case=BINDING)
    path = tmp_path / "rename_webhook.py"
    spec = importlib.util.spec_from_file_location("bound_webhook", path)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    return module


class Bus:
    def __init__(self, *, outcome=None, error=None):
        self.calls = []
        self.outcome = outcome if outcome is not None else RenameResult(True)
        self.error = error

    async def dispatch(self, command):
        self.calls.append(command)
        if self.error:
            raise self.error
        return self.outcome


def body(**changes):
    return json.dumps(
        {
            "event_type": "rename_post",
            "aggregate_id": str(uuid4()),
            "title": "New",
            **changes,
        }
    )


def headers(raw, secret=SECRET):
    return {
        "X-Webhook-Signature": hmac.new(
            secret.encode(), raw, hashlib.sha256
        ).hexdigest()
    }


@pytest.mark.asyncio
async def test_valid_signature_dispatches_exact_input_and_uuid(generated):
    raw = body()
    bus = Bus()
    webhook = generated.RenameWebhook(secret=SECRET, command_bus=bus)
    result = await webhook.handle_request(raw, headers(raw))
    assert result["status_code"] == 200
    command, target = bus.calls[0]
    assert command.title == "New"
    assert command.metadata == {}
    assert str(target) == json.loads(raw)["aggregate_id"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case",
    [
        "missing",
        "wrong",
        "body_changed",
        "caller_secret",
        "no_secret",
        "short_secret",
        "unicode_signature",
        "unsigned",
    ],
)
async def test_verification_precedes_payload_parse_and_dispatch(generated, case):
    raw = b"not even json"
    supplied = headers(raw)
    secret = SECRET
    if case == "missing":
        supplied = {}
    if case == "wrong":
        supplied = headers(raw, "wrong")
    if case == "body_changed":
        supplied = headers(body())
    if case == "caller_secret":
        supplied = {**headers(raw, "attacker"), "x-webhook-secret": "attacker"}
    if case == "unicode_signature":
        supplied = {"X-Webhook-Signature": "é" * 64}
    if case == "no_secret":
        secret = None
    if case == "short_secret":
        secret = "short"
    bus = Bus()
    if case == "unsigned":
        with pytest.raises(ValueError, match="requires signature"):
            generated.RenameWebhook(
                secret=secret, command_bus=bus, verify_signature=False
            )
        return
    result = await generated.RenameWebhook(
        secret=secret, command_bus=bus
    ).handle_request(raw, supplied)
    assert result["status_code"] in {401, 503}
    assert bus.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {"title": 42},
        {"actor_id": "attacker"},
        {"principal_sub": "attacker"},
        {"metadata": {"permission": "all"}},
        {"event_type": "other"},
        {"aggregate_id": "bad"},
        {"aggregate_id": str(uuid4()).upper()},
    ],
)
async def test_signed_invalid_schema_never_dispatches(generated, payload):
    raw = body(**payload)
    bus = Bus()
    result = await generated.RenameWebhook(
        secret=SECRET, command_bus=bus
    ).handle_request(raw, headers(raw))
    assert result["status_code"] == 422
    assert bus.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["rejected", "wrong_type", "exception", "no_bus"])
async def test_failure_is_not_success_and_details_are_not_disclosed(generated, case):
    bus = Bus(
        outcome=RenameResult(False, "private storage error")
        if case == "rejected"
        else object(),
        error=OSError("private storage error") if case == "exception" else None,
    )
    raw = body()
    webhook = generated.RenameWebhook(
        secret=SECRET, command_bus=None if case == "no_bus" else bus
    )
    result = await webhook.handle_request(raw, headers(raw))
    assert (
        result["status_code"]
        == {"rejected": 409, "wrong_type": 500, "exception": 500, "no_bus": 503}[case]
    )
    assert "private storage error" not in str(result)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("module", "x;run()"),
        ("command", "class"),
        ("inputs", ["principal_sub"]),
        ("inputs", ["metadata"]),
        ("inputs", ["title", "other"]),
        ("extra", True),
    ],
)
def test_bad_binding_refused_before_write(tmp_path, key, value):
    with pytest.raises(ValueError, match="use_case"):
        WebhookGenerator(tmp_path).generate("rename", use_case={**BINDING, key: value})
    assert not list(tmp_path.iterdir())


@pytest.mark.asyncio
async def test_same_valid_delivery_is_not_deduplicated(generated):
    raw = body()
    bus = Bus()
    hook = generated.RenameWebhook(secret=SECRET, command_bus=bus)
    for _ in range(2):
        assert (await hook.handle_request(raw, headers(raw)))["status_code"] == 200
    assert len(bus.calls) == 2


def test_hidden_command_context_is_not_implicitly_bound(generated):
    from dataclasses import make_dataclass

    generated.RenameCommand = make_dataclass(
        "WithPrincipal",
        [("principal_sub", str)],
        bases=(RenameCommand,),
        frozen=True,
        kw_only=True,
    )
    with pytest.raises(ValueError, match="no implicit context"):
        generated.RenameWebhook(secret=SECRET, command_bus=Bus())


@pytest.mark.asyncio
async def test_generated_webhook_uses_real_native_command_bus_and_handler(
    tmp_path, monkeypatch
):
    events = pytest.importorskip("quadkit.events.cli.generators.use_case")
    from quadkit.events.buses.command import CommandBusImpl
    from quadkit.result import Ok

    events.UseCaseGenerator(tmp_path).generate(
        "rename_post",
        fields_str="title:str",
        spec={
            "validate_inputs": True,
            "typed_outcomes": True,
            "writes": [{"field": "title", "source": "input.title"}],
        },
    )
    spec = importlib.util.spec_from_file_location(
        "real_rename_operation", tmp_path / "rename_post_use_case.py"
    )
    operation = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, operation)
    spec.loader.exec_module(operation)
    WebhookGenerator(tmp_path).generate(
        "real_rename",
        use_case={
            **BINDING,
            "module": spec.name,
            "command": "RenamePostCommand",
            "result": "RenamePostResult",
        },
    )
    spec = importlib.util.spec_from_file_location(
        "real_rename_webhook", tmp_path / "real_rename_webhook.py"
    )
    hook = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, hook)
    spec.loader.exec_module(hook)

    class Repository:
        def __init__(self):
            self.row = {"title": "Old"}
            self.writes = []

        async def get(self, key):
            return Ok(dict(self.row))

        async def update(self, key, values):
            self.writes.append((key, values))
            self.row.update(values)
            return Ok(dict(self.row))

    repository = Repository()
    bus = CommandBusImpl()
    bus.register(
        operation.RenamePostCommand, operation.RenamePostHandler(repository=repository)
    )
    raw = body(title="Native")
    result = await hook.RealRenameWebhook(
        secret=SECRET, command_bus=bus
    ).handle_request(raw, headers(raw))
    assert result["status_code"] == 200
    assert repository.writes == [(json.loads(raw)["aggregate_id"], {"title": "Native"})]


@pytest.mark.asyncio
@pytest.mark.parametrize("raw", [b"{", b"[]", b"null", b"\xff"])
async def test_signed_malformed_json_never_dispatches(generated, raw):
    bus = Bus()
    result = await generated.RenameWebhook(
        secret=SECRET, command_bus=bus
    ).handle_request(raw, headers(raw))
    assert result["status_code"] == 422
    assert bus.calls == []


def test_bound_output_is_lint_and_format_clean(generated):
    import subprocess

    for command in (["check"], ["format", "--check"]):
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "ruff",
                *command,
                "--isolated",
                "--config",
                "src=[]",
                "--config",
                "lint.isort.known-first-party=[]",
                generated.__file__,
            ],
            check=False,
            capture_output=True,
            text=True,
            cwd=str(Path(generated.__file__).parent),
        )
        assert result.returncode == 0, result.stdout + result.stderr
