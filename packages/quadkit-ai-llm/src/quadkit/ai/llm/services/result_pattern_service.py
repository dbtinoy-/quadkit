"""LLM client service using Result pattern for error handling."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from quadkit.ai.llm.exceptions import (
    InvalidRequestError,
    LLMError,
    ModelNotFoundError,
    ProviderConnectionError,
)
from quadkit.contracts.ai.llm import (
    ChatMessageProtocol,
    CompletionProtocol,
)
from quadkit.logging import (
    get_logger,
)
from quadkit.result import Err, Ok, Result

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from quadkit.contracts.ai import ToolDefinition

logger = get_logger(__name__)


@dataclass
class _MockCompletion:
    content: str
    model: str
    thinking: Any | None = None

    def __getitem__(self, key: str) -> Any:
        if key == "content":
            return self.content
        if key == "model":
            return self.model
        if key == "thinking":
            return self.thinking
        raise KeyError(key)


class LLMServiceWithResultPattern:
    """LLM client wrapper service using Result pattern."""

    def __init__(
        self,
        model_name: str = "gpt-4",
        max_retries: int = 3,
        timeout: float = 30.0,
    ) -> None:
        self.model_name = model_name
        self.max_retries = max_retries
        self.timeout = timeout

    async def complete(
        self,
        messages: list[ChatMessageProtocol],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        tools: list[ToolDefinition] | None = None,
        **kwargs: Any,
    ) -> Result[CompletionProtocol, LLMError]:
        del tools, kwargs
        if not messages:
            return Err(InvalidRequestError("Messages list cannot be empty"))
        if max_tokens is not None and max_tokens <= 0:
            return Err(InvalidRequestError("max_tokens must be greater than 0"))
        if temperature is not None and not (0 <= temperature <= 2):
            return Err(InvalidRequestError("temperature must be between 0 and 2"))

        model_to_use = model or self.model_name
        logger.info("llm_completion_started", message_count=len(messages))
        completion_data = _MockCompletion(
            content="This is a mock completion",
            model=model_to_use,
            thinking=None,
        )
        return Ok(completion_data)  # type: ignore[arg-type]

    async def stream_chat(
        self,
        messages: list[ChatMessageProtocol],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        tools: list[ToolDefinition] | None = None,
        **kwargs: Any,
    ) -> Result[AsyncIterator[dict[str, str]], LLMError]:
        del model, temperature, max_tokens, tools, kwargs
        if not messages:
            return Err(InvalidRequestError("Messages list cannot be empty"))

        async def mock_stream() -> AsyncIterator[dict[str, str]]:
            yield {"chunk": "Hello "}
            yield {"chunk": "world"}

        return Ok(mock_stream())

    def validate_model(self, model_name: str) -> Result[None, LLMError]:
        if not model_name:
            return Err(InvalidRequestError("Model name cannot be empty"))

        supported_models = {
            "gpt-4",
            "gpt-4-turbo",
            "gpt-3.5-turbo",
            "claude-3-opus",
            "claude-3-sonnet",
            "gemini-pro",
        }
        if model_name not in supported_models:
            return Err(ModelNotFoundError(f"Model '{model_name}' is not supported"))
        return Ok(None)

    def get_model_info(self, model_name: str) -> Result[dict[str, Any], LLMError]:
        validation_result = self.validate_model(model_name)
        if validation_result.is_err():
            return Err(validation_result.unwrap_err())

        return Ok(
            {
                "name": model_name,
                "context_window": 128000,
                "max_output_tokens": 4096,
                "supports_vision": True,
                "supports_function_calling": True,
            }
        )

    async def check_connection(
        self, timeout: float | None = None
    ) -> Result[bool, LLMError]:
        if timeout is not None and timeout <= 0:
            return Err(ProviderConnectionError("timeout must be greater than 0"))
        return Ok(True)

    async def estimate_tokens(
        self,
        text: str,
        model: str | None = None,
    ) -> Result[int, LLMError]:
        if not text:
            return Err(InvalidRequestError("Text cannot be empty"))

        model_to_use = model or self.model_name
        validation_result = self.validate_model(model_to_use)
        if validation_result.is_err():
            return Err(validation_result.unwrap_err())

        return Ok(len(text) // 4)


__all__ = ["LLMServiceWithResultPattern"]
