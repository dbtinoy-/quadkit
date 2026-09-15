"""Tests for the workflow harness, websocket test client, and pytest plugin.

Covers :class:`WorkflowTestHarness` step execution and context flow,
:class:`WebSocketTestClient` in-memory message transport, and the
quadkit pytest plugin's service-availability skip logic.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest


# ---------------------------------------------------------------------------
# WorkflowTestHarness
# ---------------------------------------------------------------------------


async def test_harness_runs_step_and_updates_context() -> None:
    from quadkit.testing.workflow.harness import WorkflowTestHarness

    harness = WorkflowTestHarness()

    async def step_a(data: dict[str, Any]) -> dict[str, Any]:
        assert data["seed"] == 1
        return {"computed": 42}

    async def step_b(data: dict[str, Any]) -> str:
        return f"done:{data['computed']}"

    result_a = await harness.run_step(step_a, input_data={"seed": 1})
    assert result_a["status"] == "completed"
    assert result_a["output"] == {"computed": 42}
    assert harness.context["computed"] == 42  # dict output merged into context

    result_b = await harness.run_step(step_b)
    assert result_b["status"] == "completed"
    assert result_b["output"] == "done:42"  # non-dict output does not merge
    assert harness.context == {"computed": 42}

    assert len(harness.step_results) == 2


async def test_harness_captures_step_failures() -> None:
    from quadkit.testing.workflow.harness import WorkflowTestHarness

    harness = WorkflowTestHarness()

    async def failing(data: dict[str, Any]) -> None:
        raise ValueError("step broke")

    result = await harness.run_step(failing, input_data={})
    assert result["status"] == "failed"
    assert "step broke" in result["error"]
    assert "output" not in result

    harness.reset()
    assert harness.step_results == []
    assert harness.context == {}


# ---------------------------------------------------------------------------
# WebSocketTestClient
# ---------------------------------------------------------------------------


async def test_websocket_client_round_trip() -> None:
    from quadkit.testing.websocket.client import WebSocketTestClient

    async with WebSocketTestClient() as ws:
        assert ws.is_connected is True
        await ws.send_json({"type": "subscribe", "channel": "order1"})
        await ws.inject_response({"type": "subscribed", "channel": "order1"})

        response = await ws.receive_json()
        assert response["type"] == "subscribed"

        assert ws.sent_messages == [{"type": "subscribe", "channel": "order1"}]
        assert ws.received_messages == [{"type": "subscribed", "channel": "order1"}]
        ws.assert_sent({"type": "subscribe", "channel": "order1"})
        with pytest.raises(AssertionError, match="not found"):
            ws.assert_sent({"type": "unsubscribe"})
    assert ws.is_connected is False


async def test_websocket_receive_times_out() -> None:
    from quadkit.testing.websocket.client import WebSocketTestClient

    ws = WebSocketTestClient()
    await ws.__aenter__()
    with pytest.raises(asyncio.TimeoutError):
        await ws.receive_json(timeout=0.01)
    await ws.__aexit__(None, None, None)


# ---------------------------------------------------------------------------
# quadkit pytest plugin (service-availability skipping)
# ---------------------------------------------------------------------------


def test_plugin_check_service_unknown_always_available() -> None:
    from quadkit.testing.plugins.pytest import _check_service

    assert _check_service("no-such-service") is True


def test_plugin_check_service_closed_port_unavailable() -> None:
    from quadkit.testing.plugins.pytest import _check_service

    # Nothing listens on the default SMTP port in this sandbox.
    assert _check_service("smtp") is False


def test_plugin_configure_registers_markers() -> None:
    from quadkit.testing.plugins.pytest import (
        _MARKERS,
        pytest_configure,
    )

    class _FakeConfig:
        def __init__(self) -> None:
            self.lines: list[tuple[str, str]] = []

        def addinivalue_line(self, name: str, line: str) -> None:
            self.lines.append((name, line))

    config = _FakeConfig()
    pytest_configure(config)  # type: ignore[arg-type]
    assert len(config.lines) == len(_MARKERS)
    assert all(name == "markers" for name, _ in config.lines)


def test_plugin_collection_skips_unavailable_services() -> None:
    from quadkit.testing.plugins.pytest import pytest_collection_modifyitems

    class _FakeMarker:
        def __init__(self, name: str) -> None:
            self.name = name

    class _FakeItem:
        def __init__(self, *markers: str) -> None:
            self._markers = [_FakeMarker(name) for name in markers]
            self.skips: list[Any] = []

        def iter_markers(self) -> list[_FakeMarker]:
            return self._markers

        def add_marker(self, marker: Any) -> None:
            self.skips.append(marker)

    item_skipped = _FakeItem("requires_smtp")
    item_plain = _FakeItem("asyncio")
    item_other = _FakeItem("requires_smtp")  # availability is cached per hook

    pytest_collection_modifyitems(None, [item_skipped, item_plain, item_other])  # type: ignore[arg-type]

    assert len(item_skipped.skips) == 1
    assert len(item_other.skips) == 1  # cached unavailable -> also skipped
    assert item_plain.skips == []
