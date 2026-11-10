"""Scenario tests for MCP controllers, provider combinators, observability
wrappers, and the logging handler.

Hermetic: no server, no transport — providers are driven directly with
decorated controller classes and fake metrics.
"""

from __future__ import annotations

from typing import Any

import pytest

from quadkit.ai.mcp.controllers import (
    ControllerPromptProvider,
    ControllerResourceProvider,
    ControllerToolProvider,
    MCPController,
    ServiceToolProvider,
    _CombinedResourceProvider,
    _CombinedToolProvider,
)
from quadkit.ai.mcp.controllers._internal import (
    _build_input_schema,
    _match_uri_pattern,
)
from quadkit.ai.mcp.controllers.decorators import prompt, resource, tool
from quadkit.ai.mcp.server.handlers.logging_handler import (
    LoggingHandler,
    _map_level,
)
from quadkit.ai.mcp.server.observability import (
    ObservableResourceHandler,
    ObservableToolHandler,
)
from quadkit.contracts.mcp.exceptions import (
    MCPPromptError,
    MCPResourceError,
    MCPToolCallError,
)
from quadkit.result import Err, Ok

# --------------------------------------------------------------------------
# Fixtures: controllers
# --------------------------------------------------------------------------


class _BaseController(MCPController):
    @tool("base_tool", description="from base")
    async def base_tool(self, value: str) -> str:
        return f"base:{value}"

    @resource("shared://{id}", description="shared thing")
    async def shared(self, id: str) -> dict[str, Any]:
        return {"uri": f"shared://{id}", "content": [{"type": "text", "text": id}]}


class _DataController(_BaseController):
    @tool("get_user", description="Fetch a user")
    async def get_user(self, user_id: str, verbose: bool = False) -> dict[str, Any]:
        return {"id": user_id, "verbose": verbose}

    @resource("users://{user_id}", description="A user record")
    async def user_record(self, user_id: str) -> dict[str, Any]:
        return {
            "uri": f"users://{user_id}",
            "content": [{"type": "text", "text": user_id}],
        }

    @resource("fixed://data", name="fixed-data", description="Static data")
    async def fixed_data(self, uri: str) -> dict[str, Any]:
        return {"uri": uri, "content": [{"type": "text", "text": "fixed"}]}

    @prompt("summarize", description="Summarize text")
    async def summarize_prompt(self, text: str) -> str:
        return f"summary of: {text}"

    @prompt("structured", description="Returns MCP format")
    async def structured_prompt(self) -> dict[str, Any]:
        return {
            "description": "structured",
            "messages": [{"role": "user", "content": {"type": "text", "text": "hi"}}],
        }

    async def _private_helper(self) -> None:
        pass


# --------------------------------------------------------------------------
# MCPController collection
# --------------------------------------------------------------------------


def test_collect_tools_inherits_and_dedupes() -> None:
    tools = _DataController.collect_tools()
    names = {t["name"] for t in tools}
    assert names == {"base_tool", "get_user"}
    by_name = {t["name"]: t for t in tools}
    assert by_name["base_tool"]["handler_name"] == "base_tool"
    assert by_name["get_user"]["description"] == "Fetch a user"
    # private methods never collected
    assert not any(t["handler_name"].startswith("_") for t in tools)


def test_collect_resources_and_prompts() -> None:
    resources = _DataController.collect_resources()
    uris = {r["uri_pattern"] for r in resources}
    assert uris == {"shared://{id}", "users://{user_id}", "fixed://data"}
    by_uri = {r["uri_pattern"]: r for r in resources}
    assert by_uri["fixed://data"]["name"] == "fixed-data"

    prompts = _DataController.collect_prompts()
    assert {p["name"] for p in prompts} == {"summarize", "structured"}


# --------------------------------------------------------------------------
# ControllerToolProvider
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_controller_tool_provider_list_and_call() -> None:
    ctrl = _DataController()
    provider = ControllerToolProvider([ctrl])
    tools = await provider.list_tools()
    by_name = {t["name"]: t for t in tools}
    assert set(by_name) == {"base_tool", "get_user"}

    schema = by_name["get_user"]["inputSchema"]
    assert schema["properties"]["user_id"] == {"type": "string"}
    # PEP 563 annotations resolve via get_type_hints -> real types
    assert schema["properties"]["verbose"] == {"type": "boolean"}
    assert schema["required"] == ["user_id"]

    result = await provider.call_tool("get_user", {"user_id": "u1", "verbose": True})
    assert result == {"id": "u1", "verbose": True}

    with pytest.raises(MCPToolCallError, match="Unknown tool"):
        await provider.call_tool("nope", {})


# --------------------------------------------------------------------------
# ControllerResourceProvider
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_controller_resource_provider_exact_and_pattern() -> None:
    ctrl = _DataController()
    provider = ControllerResourceProvider([ctrl])

    # exact URI hit
    fixed = await provider.read_resource("fixed://data")
    assert fixed["content"][0]["text"] == "fixed"

    # {var} pattern hit
    user = await provider.read_resource("users://42")
    assert user["content"][0]["text"] == "42"

    # inherited pattern hit
    shared = await provider.read_resource("shared://abc")
    assert shared["content"][0]["text"] == "abc"

    with pytest.raises(MCPResourceError, match="No resource registered"):
        await provider.read_resource("unknown://1")


@pytest.mark.asyncio
async def test_controller_resource_provider_templates_and_listing() -> None:
    provider = ControllerResourceProvider([_DataController()])
    resources = await provider.list_resources()
    assert {r["uri"] for r in resources} == {
        "shared://{id}",
        "users://{user_id}",
        "fixed://data",
    }
    templates = await provider.list_templates()
    assert {t["uriTemplate"] for t in templates} == {
        "shared://{id}",
        "users://{user_id}",
    }


# --------------------------------------------------------------------------
# ControllerPromptProvider
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_controller_prompt_provider_dispatch() -> None:
    provider = ControllerPromptProvider([_DataController()])
    prompts = await provider.list_prompts()
    assert {p["name"] for p in prompts} == {"summarize", "structured"}

    # str handler result -> MCP message envelope
    result = await provider.get_prompt("summarize", {"text": "abc"})
    assert result["messages"] == [
        {"role": "user", "content": {"type": "text", "text": "summary of: abc"}}
    ]

    # dict handler result passes through untouched
    structured = await provider.get_prompt("structured")
    assert structured["messages"][0]["content"]["text"] == "hi"

    with pytest.raises(MCPPromptError, match="Unknown prompt"):
        await provider.get_prompt("nope")


# --------------------------------------------------------------------------
# ServiceToolProvider
# --------------------------------------------------------------------------


class _UserService:
    """User service."""

    async def search_users(self, q: str) -> list[str]:
        """Search users by query."""
        return [q]

    def get_count(self) -> int:
        """Count users."""
        return 7

    def _hidden(self) -> None:
        pass


class _AnalyticsService:
    """Analytics service."""

    async def fetch_report(self, kind: str = "daily") -> str:
        """Fetch a report."""
        return f"{kind}-report"


@pytest.mark.asyncio
async def test_service_tool_provider_discovery_and_dispatch() -> None:
    user_svc = _UserService()
    provider = ServiceToolProvider.from_services(user_svc)
    tools = await provider.list_tools()
    names = {t["name"] for t in tools}
    assert names == {"userservice_search_users", "userservice_get_count"}
    by_name = {t["name"]: t for t in tools}
    assert (
        by_name["userservice_search_users"]["description"] == "Search users by query."
    )
    assert by_name["userservice_get_count"]["inputSchema"]["type"] == "object"

    # async method
    assert await provider.call_tool("userservice_search_users", {"q": "bob"}) == ["bob"]
    # sync method
    assert await provider.call_tool("userservice_get_count", {}) == 7

    with pytest.raises(MCPToolCallError, match="Unknown tool"):
        await provider.call_tool("userservice_nope", {})


@pytest.mark.asyncio
async def test_service_tool_provider_list_and_include_patterns() -> None:
    user_svc = _UserService()
    analytics = _AnalyticsService()

    provider = ServiceToolProvider.from_services([user_svc, analytics])
    names = {t["name"] for t in await provider.list_tools()}
    assert names == {
        "userservice_search_users",
        "userservice_get_count",
        "analyticsservice_fetch_report",
    }
    # dispatch routes to the owning instance
    assert (
        await provider.call_tool("analyticsservice_fetch_report", {"kind": "weekly"})
        == "weekly-report"
    )

    filtered = ServiceToolProvider.from_services(
        [user_svc, analytics], include_patterns=["search*"]
    )
    assert {t["name"] for t in await filtered.list_tools()} == {
        "userservice_search_users"
    }


# --------------------------------------------------------------------------
# Combinators
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_combined_tool_provider_aggregation_and_routing() -> None:
    ctrl = _DataController()
    tool_provider = ControllerToolProvider([ctrl])
    service_provider = ServiceToolProvider.from_services(_UserService())

    combined = _CombinedToolProvider([tool_provider, service_provider])
    names = {t["name"] for t in await combined.list_tools()}
    assert names == {
        "base_tool",
        "get_user",
        "userservice_search_users",
        "userservice_get_count",
    }

    assert await combined.call_tool("get_user", {"user_id": "x"}) == {
        "id": "x",
        "verbose": False,
    }
    assert await combined.call_tool("userservice_get_count", {}) == 7

    with pytest.raises(MCPToolCallError, match="Unknown tool"):
        await combined.call_tool("ghost", {})


@pytest.mark.asyncio
async def test_combined_resource_provider_aggregation_and_routing() -> None:
    ctrl = _DataController()
    resource_provider = ControllerResourceProvider([ctrl])
    combined = _CombinedResourceProvider([None, resource_provider, None])

    resources = await combined.list_resources()
    assert any(r["uri"] == "users://{user_id}" for r in resources)
    got = await combined.read_resource("users://9")
    assert got["content"][0]["text"] == "9"

    with pytest.raises(MCPResourceError, match="Unknown resource URI"):
        await combined.read_resource("missing://x")


# --------------------------------------------------------------------------
# Internal helpers
# --------------------------------------------------------------------------


def test_build_input_schema_type_map() -> None:
    def sample(a: str, b: int = 1) -> None:  # noqa: B008
        pass

    schema = _build_input_schema(sample)
    assert schema["properties"] == {
        "a": {"type": "string"},
        "b": {"type": "integer"},
    }
    assert schema["required"] == ["a"]


def test_build_input_schema_untyped_defaults_string() -> None:
    def sample(e=None, f=None) -> None:
        pass

    schema = _build_input_schema(sample)
    # annotations missing from _TYPE_MAP fall back to "string"
    assert schema["properties"] == {"e": {"type": "string"}, "f": {"type": "string"}}
    assert "required" not in schema


def test_build_input_schema_self_skipped() -> None:
    def method(self: Any, x: str) -> None:
        pass

    schema = _build_input_schema(method)
    assert "self" not in schema["properties"]


def test_match_uri_pattern() -> None:
    assert _match_uri_pattern("users://{user_id}", "users://123") == {"user_id": "123"}
    assert _match_uri_pattern("a://{x}/b/{y}", "a://1/b/2") == {"x": "1", "y": "2"}
    assert _match_uri_pattern("users://{user_id}", "orders://123") is None
    assert _match_uri_pattern("fixed://x", "fixed://y") is None


# --------------------------------------------------------------------------
# Observability wrappers
# --------------------------------------------------------------------------


class _FakeCounter:
    def __init__(self) -> None:
        self.increments: list[dict[str, str]] = []

    def increment(
        self, labels: dict[str, str] | None = None, amount: float = 1
    ) -> None:
        self.increments.append(dict(labels or {}))


class _FakeHistogram:
    def __init__(self) -> None:
        self.observations: list[tuple[float, dict[str, str]]] = []

    def observe(self, value: float, labels: dict[str, str] | None = None) -> None:
        self.observations.append((value, dict(labels or {})))


class _FakeCollector:
    def __init__(self) -> None:
        self.counters: dict[str, _FakeCounter] = {}
        self.histogram_buckets: dict[str, list[float]] = {}

    def create_counter(self, name: str, description: str = "") -> _FakeCounter:
        return self.counters.setdefault(name, _FakeCounter())

    def create_histogram(
        self, name: str, description: str = "", buckets: list[float] | None = None
    ) -> _FakeHistogram:
        if buckets:
            self.histogram_buckets[name] = buckets
        return _FakeHistogram()


class _FakeMetrics:
    def __init__(self) -> None:
        self._collector = _FakeCollector()


class _FakeToolHandler:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail

    async def list_tools(self) -> dict[str, Any]:
        return {"tools": [{"name": "fake_tool"}]}

    async def call_tool(self, name: str, arguments: Any = None) -> Any:
        if self.fail:
            return Err(MCPToolCallError(message="boom", tool_name=name))
        return Ok({"name": name})


class _FakeResourceHandler:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail

    async def list_resources(self) -> dict[str, Any]:
        return {"resources": []}

    async def list_templates(self) -> dict[str, Any]:
        return {"templates": []}

    async def read_resource(self, uri: str) -> dict[str, Any]:
        if self.fail:
            raise ValueError("read exploded")
        return {"uri": uri, "content": []}


@pytest.mark.asyncio
async def test_observable_tool_handler_success_and_error() -> None:
    metrics = _FakeMetrics()
    wrapper = ObservableToolHandler(_FakeToolHandler(), metrics)
    assert await wrapper.list_tools() == {"tools": [{"name": "fake_tool"}]}

    assert (await wrapper.call_tool("t1")).is_ok()
    assert metrics._collector.counters["mcp_tool_calls_total"].increments == [
        {"tool": "t1", "status": "success"}
    ]
    assert metrics._collector.histogram_buckets["mcp_tool_call_duration_seconds"]
    assert metrics._collector.counters["mcp_errors_total"].increments == []

    failing = ObservableToolHandler(_FakeToolHandler(fail=True), metrics)
    assert (await failing.call_tool("t2")).is_err()
    calls = metrics._collector.counters["mcp_tool_calls_total"].increments
    assert calls[-1] == {"tool": "t2", "status": "error"}
    errors = metrics._collector.counters["mcp_errors_total"].increments
    assert errors[-1] == {"operation": "tool_call", "error_type": "MCPToolCallError"}


@pytest.mark.asyncio
async def test_observable_resource_handler_scheme_and_errors() -> None:
    metrics = _FakeMetrics()
    wrapper = ObservableResourceHandler(_FakeResourceHandler(), metrics)
    assert await wrapper.list_resources() == {"resources": []}
    assert await wrapper.list_templates() == {"templates": []}

    got = await wrapper.read_resource("file://etc/hosts")
    assert got["uri"] == "file://etc/hosts"
    reads = metrics._collector.counters["mcp_resource_reads_total"].increments
    assert reads == [{"scheme": "file", "status": "success"}]

    # URIs without a scheme map to "unknown"
    await wrapper.read_resource("plainname")
    assert metrics._collector.counters["mcp_resource_reads_total"].increments[-1] == {
        "scheme": "unknown",
        "status": "success",
    }

    # errors are counted AND re-raised
    failing = ObservableResourceHandler(_FakeResourceHandler(fail=True), metrics)
    with pytest.raises(ValueError, match="read exploded"):
        await failing.read_resource("mem://x")
    reads = metrics._collector.counters["mcp_resource_reads_total"].increments
    assert reads[-1] == {"scheme": "mem", "status": "error"}
    errors = metrics._collector.counters["mcp_errors_total"].increments
    assert errors[-1] == {"operation": "resource_read", "error_type": "ValueError"}


# --------------------------------------------------------------------------
# LoggingHandler
# --------------------------------------------------------------------------


def test_logging_handler_invalid_level() -> None:
    with pytest.raises(ValueError, match="Invalid MCP log level"):
        LoggingHandler(min_level="verbose")
    assert _map_level("emergency") == "critical"
    assert _map_level("notice") == "info"
    assert _map_level("bogus") == "info"


@pytest.mark.asyncio
async def test_logging_handler_set_level() -> None:
    handler = LoggingHandler()
    assert (await handler.set_level("warning")).is_ok()
    # invalid level falls back to info
    assert (await handler.set_level("bogus")).is_ok()


@pytest.mark.asyncio
async def test_logging_handler_level_filtering() -> None:
    notifications: list[dict[str, Any]] = []

    async def notify(notification: dict[str, Any]) -> None:
        notifications.append(notification)

    handler = LoggingHandler(min_level="warning")
    handler.set_notify_callback(notify)

    await handler.log("info", "too low")
    assert notifications == []
    await handler.log("warning", "just right", data={"k": "v"}, logger_name="svc")
    assert len(notifications) == 1
    note = notifications[0]
    assert note["method"] == "notifications/message"
    assert note["params"]["level"] == "warning"
    assert note["params"]["data"] == {"k": "v"}
    assert note["params"]["logger"] == "svc"

    # dynamic level change takes effect
    await handler.set_level("emergency")
    await handler.log("error", "now too low")
    assert len(notifications) == 1
    await handler.log("emergency", "top")
    assert len(notifications) == 2


@pytest.mark.asyncio
async def test_logging_handler_does_not_log_client_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from unittest.mock import MagicMock

    import quadkit.ai.mcp.server.handlers.logging_handler as logging_handler_module

    mock_logger = MagicMock()
    monkeypatch.setattr(logging_handler_module, "logger", mock_logger)
    sentinel = "SENTINEL-sensitive-client-log"

    await LoggingHandler().log(
        "info",
        sentinel,
        data={"credential": sentinel},
        logger_name=sentinel,
    )

    mock_logger.info.assert_called_once_with("mcp_client_log", level="info")
    assert sentinel not in str(mock_logger.info.call_args)


@pytest.mark.asyncio
async def test_logging_handler_callback_failure_swallowed() -> None:
    async def broken(notification: dict[str, Any]) -> None:
        raise RuntimeError("transport down")

    handler = LoggingHandler()
    handler.set_notify_callback(broken)
    # must not raise — log notification is best-effort
    await handler.log("error", "still local")


@pytest.mark.asyncio
async def test_logging_handler_unknown_level_dropped() -> None:
    # log() validates the level up front: unknown levels are silently
    # dropped (no local log, no client notification)
    notifications: list[dict[str, Any]] = []
    handler = LoggingHandler()
    handler.set_notify_callback(_capture(notifications))
    await handler.log("trace", "weird level")
    assert notifications == []


def test_logging_handler_filter_unknown_levels_drop() -> None:
    # Unknown MCP levels are not forwarded or written locally.
    handler = LoggingHandler(min_level="warning")
    assert handler._is_at_or_above_min("weird") is False  # noqa: SLF001
    assert handler._is_at_or_above_min("debug") is False  # noqa: SLF001
    assert handler._is_at_or_above_min("critical") is True  # noqa: SLF001


def _capture(target: list[Any]) -> Any:
    async def cb(notification: Any) -> None:
        target.append(notification)

    return cb
