"""Tests for Result pattern implementation in LLM service.

Verifies that LLM operations return Result[T, LLMError] types
instead of bare values or raising exceptions.
"""

from __future__ import annotations

import pytest
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from quadkit.ai.llm.exceptions import (
    LLMError,
    LLMAuthenticationError,
    InvalidRequestError,
    ModelNotFoundError,
    LLMRateLimitError,
    TokenLimitError,
    ProviderConnectionError,
    StreamError,
)
from quadkit.result import Result
from quadkit.ai.llm.services import LLMServiceWithResultPattern


class MockChatMessage:
    """Mock chat message for testing."""

    def __init__(self, role: str, content: str) -> None:
        """Initialize mock message."""
        self.role = role
        self.content = content


class TestLLMServiceResultPattern:
    """Test Result pattern in LLM service."""

    @pytest.fixture
    def llm_service(self) -> LLMServiceWithResultPattern:
        """Create a fresh LLM service for each test."""
        return LLMServiceWithResultPattern(
            model_name="gpt-4",
            max_retries=3,
            timeout=30.0,
        )

    @pytest.fixture
    def mock_messages(self) -> list[MockChatMessage]:
        """Create mock chat messages."""
        return [
            MockChatMessage("system", "You are a helpful assistant."),
            MockChatMessage("user", "Hello, how are you?"),
        ]

    @pytest.mark.asyncio
    async def test_complete_returns_ok_for_valid_messages(
        self,
        llm_service: LLMServiceWithResultPattern,
        mock_messages: list[MockChatMessage],
    ) -> None:
        """Verify complete returns Ok for valid messages."""
        result = await llm_service.complete(
            messages=mock_messages,
            model="gpt-4",
            temperature=0.7,
            max_tokens=100,
        )

        assert result.is_ok()
        completion = result.unwrap()
        assert completion["content"] is not None
        assert completion["model"] == "gpt-4"

    @pytest.mark.asyncio
    async def test_complete_returns_err_for_empty_messages(
        self,
        llm_service: LLMServiceWithResultPattern,
    ) -> None:
        """Verify complete returns Err for empty messages."""
        result = await llm_service.complete(messages=[])

        assert result.is_err()
        error = result.unwrap_err()
        assert isinstance(error, InvalidRequestError)

    @pytest.mark.asyncio
    async def test_complete_returns_err_for_invalid_temperature(
        self,
        llm_service: LLMServiceWithResultPattern,
        mock_messages: list[MockChatMessage],
    ) -> None:
        """Verify complete returns Err for invalid temperature."""
        result = await llm_service.complete(
            messages=mock_messages,
            temperature=3.0,  # Out of range
        )

        assert result.is_err()
        error = result.unwrap_err()
        assert isinstance(error, InvalidRequestError)

    @pytest.mark.asyncio
    async def test_complete_returns_err_for_invalid_max_tokens(
        self,
        llm_service: LLMServiceWithResultPattern,
        mock_messages: list[MockChatMessage],
    ) -> None:
        """Verify complete returns Err for invalid max_tokens."""
        result = await llm_service.complete(
            messages=mock_messages,
            max_tokens=-1,  # Invalid
        )

        assert result.is_err()
        error = result.unwrap_err()
        assert isinstance(error, InvalidRequestError)

    @pytest.mark.asyncio
    async def test_stream_chat_returns_ok_for_valid_messages(
        self,
        llm_service: LLMServiceWithResultPattern,
        mock_messages: list[MockChatMessage],
    ) -> None:
        """Verify stream_chat returns Ok for valid messages."""
        result = await llm_service.stream_chat(
            messages=mock_messages,
            model="gpt-4",
        )

        assert result.is_ok()
        stream = result.unwrap()
        assert stream is not None

    @pytest.mark.asyncio
    async def test_stream_chat_returns_err_for_empty_messages(
        self,
        llm_service: LLMServiceWithResultPattern,
    ) -> None:
        """Verify stream_chat returns Err for empty messages."""
        result = await llm_service.stream_chat(messages=[])

        assert result.is_err()
        error = result.unwrap_err()
        assert isinstance(error, InvalidRequestError)

    @pytest.mark.asyncio
    async def test_validate_model_returns_ok_for_valid_model(
        self,
        llm_service: LLMServiceWithResultPattern,
    ) -> None:
        """Verify validate_model returns Ok for valid model."""
        result = llm_service.validate_model("gpt-4")

        assert result.is_ok()

    @pytest.mark.asyncio
    async def test_validate_model_returns_err_for_invalid_model(
        self,
        llm_service: LLMServiceWithResultPattern,
    ) -> None:
        """Verify validate_model returns Err for unsupported model."""
        result = llm_service.validate_model("unknown-model")

        assert result.is_err()
        error = result.unwrap_err()
        assert isinstance(error, ModelNotFoundError)

    @pytest.mark.asyncio
    async def test_validate_model_returns_err_for_empty_model(
        self,
        llm_service: LLMServiceWithResultPattern,
    ) -> None:
        """Verify validate_model returns Err for empty model name."""
        result = llm_service.validate_model("")

        assert result.is_err()
        error = result.unwrap_err()
        assert isinstance(error, InvalidRequestError)

    @pytest.mark.asyncio
    async def test_get_model_info_returns_ok_for_valid_model(
        self,
        llm_service: LLMServiceWithResultPattern,
    ) -> None:
        """Verify get_model_info returns Ok for valid model."""
        result = llm_service.get_model_info("gpt-4")

        assert result.is_ok()
        info = result.unwrap()
        assert info["name"] == "gpt-4"
        assert "context_window" in info
        assert "max_output_tokens" in info

    @pytest.mark.asyncio
    async def test_get_model_info_returns_err_for_invalid_model(
        self,
        llm_service: LLMServiceWithResultPattern,
    ) -> None:
        """Verify get_model_info returns Err for unsupported model."""
        result = llm_service.get_model_info("unknown-model")

        assert result.is_err()
        error = result.unwrap_err()
        assert isinstance(error, (ModelNotFoundError, LLMError))

    @pytest.mark.asyncio
    async def test_check_connection_returns_ok(
        self,
        llm_service: LLMServiceWithResultPattern,
    ) -> None:
        """Verify check_connection returns Ok."""
        result = await llm_service.check_connection()

        assert result.is_ok()
        assert result.unwrap() is True

    @pytest.mark.asyncio
    async def test_estimate_tokens_returns_ok_for_valid_text(
        self,
        llm_service: LLMServiceWithResultPattern,
    ) -> None:
        """Verify estimate_tokens returns Ok for valid text."""
        result = await llm_service.estimate_tokens("Hello world!")

        assert result.is_ok()
        tokens = result.unwrap()
        assert isinstance(tokens, int)
        assert tokens > 0

    @pytest.mark.asyncio
    async def test_estimate_tokens_returns_err_for_empty_text(
        self,
        llm_service: LLMServiceWithResultPattern,
    ) -> None:
        """Verify estimate_tokens returns Err for empty text."""
        result = await llm_service.estimate_tokens("")

        assert result.is_err()
        error = result.unwrap_err()
        assert isinstance(error, InvalidRequestError)

    @pytest.mark.asyncio
    async def test_estimate_tokens_returns_err_for_invalid_model(
        self,
        llm_service: LLMServiceWithResultPattern,
    ) -> None:
        """Verify estimate_tokens returns Err for invalid model."""
        result = await llm_service.estimate_tokens(
            "Hello world!",
            model="unknown-model",
        )

        assert result.is_err()
        error = result.unwrap_err()
        assert isinstance(error, (ModelNotFoundError, LLMError))

    @pytest.mark.asyncio
    async def test_error_hierarchy_correct(self) -> None:
        """Verify error hierarchy is correct."""
        from quadkit.contracts.exceptions.domain import DomainError

        # All LLM errors inherit from DomainError
        assert issubclass(LLMError, DomainError)
        assert issubclass(LLMAuthenticationError, LLMError)
        assert issubclass(InvalidRequestError, LLMError)
        assert issubclass(ModelNotFoundError, LLMError)
        assert issubclass(LLMRateLimitError, LLMError)

        # Instantiate and verify
        llm_err = LLMError("test")
        assert isinstance(llm_err, DomainError)

        auth_err = LLMAuthenticationError("auth failed")
        assert isinstance(auth_err, LLMError)
        assert isinstance(auth_err, DomainError)

    @pytest.mark.asyncio
    async def test_result_type_available(self) -> None:
        """Verify Result type is available for import."""
        assert Result is not None

        # Verify generic form works
        result_type = Result[dict, LLMError]
        assert result_type is not None

    @pytest.mark.asyncio
    async def test_default_model_used_when_none_provided(
        self,
        llm_service: LLMServiceWithResultPattern,
        mock_messages: list[MockChatMessage],
    ) -> None:
        """Verify default model is used when none provided."""
        result = await llm_service.complete(messages=mock_messages)

        assert result.is_ok()
        completion = result.unwrap()
        assert completion["model"] == "gpt-4"  # default

    @pytest.mark.asyncio
    async def test_model_override_used_when_provided(
        self,
        llm_service: LLMServiceWithResultPattern,
        mock_messages: list[MockChatMessage],
    ) -> None:
        """Verify provided model overrides default."""
        result = await llm_service.complete(
            messages=mock_messages,
            model="gpt-3.5-turbo",
        )

        assert result.is_ok()
        completion = result.unwrap()
        assert completion["model"] == "gpt-3.5-turbo"

    @pytest.mark.asyncio
    async def test_multiple_supported_models(
        self,
        llm_service: LLMServiceWithResultPattern,
    ) -> None:
        """Verify multiple models are supported."""
        models = [
            "gpt-4",
            "gpt-4-turbo",
            "gpt-3.5-turbo",
            "claude-3-opus",
            "claude-3-sonnet",
            "gemini-pro",
        ]

        for model in models:
            result = llm_service.validate_model(model)
            assert result.is_ok(), f"Model {model} should be valid"


class TestLLMErrorInstantiation:
    """Test LLM error instantiation."""

    def test_llm_error_with_message(self) -> None:
        """Verify LLMError includes message."""
        error = LLMError("Something went wrong")
        assert "Something went wrong" in str(error)

    def test_authentication_error(self) -> None:
        """Verify LLMAuthenticationError works."""
        error = LLMAuthenticationError("Auth failed")
        assert isinstance(error, LLMError)

    def test_model_not_found_error(self) -> None:
        """Verify ModelNotFoundError works."""
        error = ModelNotFoundError("Model not found")
        assert isinstance(error, LLMError)

    def test_rate_limit_error(self) -> None:
        """Verify LLMRateLimitError works."""
        error = LLMRateLimitError("Rate limited")
        assert isinstance(error, LLMError)

    def test_token_limit_error(self) -> None:
        """Verify TokenLimitError works."""
        error = TokenLimitError("Token limit exceeded")
        assert isinstance(error, LLMError)

    def test_provider_connection_error(self) -> None:
        """Verify ProviderConnectionError works."""
        error = ProviderConnectionError("Connection failed")
        assert isinstance(error, LLMError)


__all__ = [
    "TestLLMServiceResultPattern",
    "TestLLMErrorInstantiation",
]
