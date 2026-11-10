"""Tests for DraftVerifyExecutor."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.ai.agents.speculation.draft_verify import DraftVerifyExecutor
from quadkit.contracts.ai.llm import ChatMessage, Completion
from quadkit.result import Ok


class TestDraftVerifyExecutor:
    """Tests for DraftVerifyExecutor."""

    @pytest.fixture
    def mock_draft(self) -> MagicMock:
        client = MagicMock()
        client.complete = AsyncMock(return_value=Ok(Completion(content="draft response", model="gpt-4", finish_reason="stop")))
        return client

    @pytest.fixture
    def mock_verify(self) -> MagicMock:
        client = MagicMock()
        client.complete = AsyncMock(return_value=Ok(Completion(content="yes correct", model="gpt-4", finish_reason="stop")))
        return client

    @pytest.fixture
    def mock_pro(self) -> MagicMock:
        client = MagicMock()
        client.complete = AsyncMock(return_value=Ok(Completion(content="pro response", model="gpt-4", finish_reason="stop")))
        return client

    @pytest.fixture
    def executor(self, mock_draft: MagicMock, mock_verify: MagicMock, mock_pro: MagicMock) -> DraftVerifyExecutor:
        return DraftVerifyExecutor(mock_draft, mock_verify, mock_pro)

    @pytest.mark.asyncio
    async def test_execute_returns_draft_when_verified(self, executor: DraftVerifyExecutor, mock_pro: MagicMock) -> None:
        result = await executor.execute(
            [ChatMessage(role="user", content="hello")],
        )
        assert result.is_ok()
        assert result.unwrap().content == "draft response"

    @pytest.mark.asyncio
    async def test_execute_uses_pro_when_draft_rejected(
        self,
        mock_verify: MagicMock,
        mock_pro: MagicMock,
    ) -> None:
        mock_verify.complete = AsyncMock(return_value=Ok(Completion(content="no incorrect", model="gpt-4", finish_reason="stop")))
        mock_pro.complete = AsyncMock(return_value=Ok(Completion(content="pro response", model="gpt-4", finish_reason="stop")))

        executor = DraftVerifyExecutor(
            MagicMock(complete=AsyncMock(return_value=Ok(Completion(content="draft", model="gpt-4", finish_reason="stop")))),
            mock_verify,
            mock_pro,
        )
        result = await executor.execute(
            [ChatMessage(role="user", content="hello")],
        )
        assert result.is_ok()
        assert result.unwrap().content == "pro response"

    @pytest.mark.asyncio
    async def test_execute_forwards_model_and_temp_to_pro(self, mock_pro: MagicMock, executor: DraftVerifyExecutor) -> None:
        await executor.execute(
            [ChatMessage(role="user", content="hello")],
            model="gpt-4",
            temperature=0.5,
            max_tokens=100,
        )
        mock_pro.complete.assert_called_once()
        _, kwargs = mock_pro.complete.call_args
        assert kwargs.get("model") == "gpt-4"
        assert kwargs.get("temperature") == 0.5
        assert kwargs.get("max_tokens") == 100

    @pytest.mark.asyncio
    async def test_execute_returns_error_when_draft_fails(self, mock_draft: MagicMock, mock_pro: MagicMock) -> None:
        from quadkit.result import Err
        from quadkit.contracts.ai.exceptions import LLMError

        mock_draft.complete = AsyncMock(return_value=Err(LLMError("draft failed")))

        executor = DraftVerifyExecutor(mock_draft, mock_pro, mock_pro)
        result = await executor.execute(
            [ChatMessage(role="user", content="hello")],
        )
        assert result.is_err()
