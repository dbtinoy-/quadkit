"""Regression tests for OpenTelemetry guards in monitor instrumentation modules."""

from __future__ import annotations

import builtins
import importlib
from types import SimpleNamespace

import pytest

DB_MODULE = "quadkit.monitor.instrumentation.database"
MSG_MODULE = "quadkit.monitor.instrumentation.messaging"


def _reload_with_blocked_import(module_name: str, blocked: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Reload a module with a third-party root import blocked."""

    real_import = builtins.__import__

    def fake_import(name: str, *args: object, **kwargs: object) -> object:
        if name == blocked or name.startswith(f"{blocked}."):
            raise ImportError(f"blocked import: {name}")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    module = importlib.import_module(module_name)
    importlib.reload(module)
    monkeypatch.undo()
    return module


def test_database_module_imports_without_opentelemetry(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _reload_with_blocked_import(DB_MODULE, "opentelemetry", monkeypatch)
    assert module._opentelemetry_available is False
    importlib.reload(module)


def test_instrument_database_noop_without_otel(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _reload_with_blocked_import(DB_MODULE, "opentelemetry", monkeypatch)
    provider = SimpleNamespace(execute=lambda *_: None)
    module.instrument_database(provider)
    assert not hasattr(provider, "_traced")
    importlib.reload(module)


def test_instrument_database_wraps_provider_when_otel_present(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("opentelemetry")
    module = importlib.import_module(DB_MODULE)
    assert module._opentelemetry_available is True

    async def execute(sql: str, params: object = None) -> str:
        return "ok"

    provider = SimpleNamespace(execute=execute, url="sqlite:///test.db", config=SimpleNamespace(name="test"))
    module.instrument_database(provider)
    assert provider._traced is True
    import asyncio

    assert asyncio.run(provider.execute("SELECT 1")) == "ok"


def test_messaging_module_imports_without_opentelemetry(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _reload_with_blocked_import(MSG_MODULE, "opentelemetry", monkeypatch)
    assert module._opentelemetry_available is False
    importlib.reload(module)


@pytest.mark.asyncio
async def test_trace_publish_noop_without_otel(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _reload_with_blocked_import(MSG_MODULE, "opentelemetry", monkeypatch)
    async with module.trace_publish("notifications", "email") as span:
        assert span is not None
    importlib.reload(module)


@pytest.mark.asyncio
async def test_trace_consume_noop_without_otel(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _reload_with_blocked_import(MSG_MODULE, "opentelemetry", monkeypatch)
    async with module.trace_consume("notifications", carrier={"traceparent": "x"}) as span:
        assert span is not None
    importlib.reload(module)


def test_inject_trace_context_noop_without_otel(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _reload_with_blocked_import(MSG_MODULE, "opentelemetry", monkeypatch)
    carrier: dict[str, object] = {}
    module.inject_trace_context(carrier)
    assert carrier == {}
    importlib.reload(module)
