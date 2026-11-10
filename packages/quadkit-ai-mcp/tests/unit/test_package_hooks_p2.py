"""P2 hook surface import verification for quadkit-ai-mcp."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, is_dataclass

import pytest


def test_mcp_hooks_root_module_exists() -> None:
    import quadkit.ai.mcp
    from quadkit.ai.mcp.hooks import (
        MCPServerStartedHook,
        MCPServerStoppedHook,
        MCPToolInvokedHook,
    )

    assert MCPServerStartedHook.__name__ == "MCPServerStartedHook"
    assert MCPServerStoppedHook.__name__ == "MCPServerStoppedHook"
    assert MCPToolInvokedHook.__name__ == "MCPToolInvokedHook"
    assert quadkit.ai.mcp.MCPServerStartedHook is MCPServerStartedHook
    assert quadkit.ai.mcp.MCPServerStoppedHook is MCPServerStoppedHook
    assert quadkit.ai.mcp.MCPToolInvokedHook is MCPToolInvokedHook


def test_mcp_hook_payloads_are_frozen_and_keyword_only() -> None:
    from quadkit.ai.mcp.hooks import (
        MCPServerStartedHook,
        MCPServerStoppedHook,
        MCPToolInvokedHook,
    )

    started = MCPServerStartedHook(transport="stdio")
    stopped = MCPServerStoppedHook(transport="stdio")
    invoked = MCPToolInvokedHook(tool_name="search")

    assert is_dataclass(started)
    assert is_dataclass(stopped)
    assert is_dataclass(invoked)

    with pytest.raises(TypeError):
        MCPServerStartedHook("stdio")  # type: ignore[misc]

    with pytest.raises(FrozenInstanceError):
        started.transport = "sse"  # type: ignore[misc]

    with pytest.raises(TypeError):
        MCPServerStoppedHook("stdio")  # type: ignore[misc]

    with pytest.raises(FrozenInstanceError):
        stopped.transport = "sse"  # type: ignore[misc]

    with pytest.raises(TypeError):
        MCPToolInvokedHook("search")  # type: ignore[misc]

    with pytest.raises(FrozenInstanceError):
        invoked.tool_name = "other"  # type: ignore[misc]
