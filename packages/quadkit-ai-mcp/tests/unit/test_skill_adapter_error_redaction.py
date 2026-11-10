"""Regression tests for MCP skill adapter error privacy."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.ai.mcp.adapters.skill_adapter import SkillToolAdapter
from quadkit.result import Err


@pytest.mark.asyncio
async def test_skill_execution_error_hides_private_input_and_error_text() -> None:
    private_detail = "api_key=sk-private /srv/tenant-42/private.txt"
    registry = MagicMock()
    registry.get.return_value = object()
    executor = MagicMock()
    executor.execute = AsyncMock(return_value=Err(RuntimeError(private_detail)))
    adapter = SkillToolAdapter(registry, executor)

    with pytest.raises(RuntimeError) as exc_info:
        await adapter.call_tool(
            name="private-skill-name",
            arguments={"secret": private_detail},
            user_id="private-user-id",
            session_id="private-session-id",
        )

    message = str(exc_info.value)
    assert "RuntimeError" in message
    assert private_detail not in message
    assert "sk-private" not in message
    assert "/srv/tenant-42/private.txt" not in message
    assert "private-skill-name" not in message
    assert "private-user-id" not in message
    assert "private-session-id" not in message
    assert exc_info.value.__cause__ is None


@pytest.mark.asyncio
async def test_missing_skill_error_does_not_echo_requested_name() -> None:
    registry = MagicMock()
    registry.get.return_value = None
    adapter = SkillToolAdapter(registry, MagicMock())

    with pytest.raises(ValueError) as exc_info:
        await adapter.call_tool("private-skill-name", {})

    assert "private-skill-name" not in str(exc_info.value)
