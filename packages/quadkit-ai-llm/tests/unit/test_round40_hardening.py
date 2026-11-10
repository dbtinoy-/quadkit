"""Round 40 hardening pins — ai-llm: client failures map to typed errors.

AnthropicClient._do_complete — when the SDK fails with a non-builtin
driver error type, the failure is classified (infrastructure AIError)
instead of escaping as the raw driver error.

Run with: pytest tests/unit/test_round40_hardening.py -v
"""

from __future__ import annotations

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from quadkit.ai.llm.clients.anthropic import AnthropicClient
from quadkit.ai.llm.config import ClientConfig
from quadkit.ai.llm.types import ChatMessage
from quadkit.contracts.ai.llm import Role
from quadkit.contracts.ai.exceptions import AIError


class _DriverError(Exception):
    """Stand-in for an LLM SDK error type (not ValueError/RuntimeError/OSError)."""


class TestAnthropicDriverErrorClassification:
    def _make_client(self) -> tuple[AnthropicClient, MagicMock]:
        mock_anthropic = MagicMock()
        mock_async_client = MagicMock()
        mock_anthropic.AsyncAnthropic = lambda **_: mock_async_client
        with patch.dict(sys.modules, {"anthropic": mock_anthropic}):
            client = AnthropicClient(config=ClientConfig(model="claude-3-sonnet-20240229"))
        return client, mock_async_client

    @pytest.mark.asyncio
    async def test_driver_error_becomes_classified_ai_error(self) -> None:
        client, sdk = self._make_client()
        sdk.messages.create = AsyncMock(side_effect=_DriverError("sdk wedged"))

        with pytest.raises(AIError):
            await client._do_complete(messages=[ChatMessage(role=Role.USER, content="hi")])
