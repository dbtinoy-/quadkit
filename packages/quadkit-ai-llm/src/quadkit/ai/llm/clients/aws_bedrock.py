"""AWS Bedrock LLM client for the Quadkit LLM routing system.

Implements the :class:`~quadkit.contracts.ai.protocols.LLMClientProtocol`
protocol against the AWS Bedrock ``Converse`` API.  The ``Converse`` API
provides a unified interface for all Bedrock models and natively supports
multi-turn conversations and tool (function) calling.

Authentication and request signing use the ``boto3``/``botocore`` AWS SDK,
which honours the standard AWS credential chain (environment variables, shared
credentials file, EC2 instance profile, ECS task role, etc.).

Configuration is sourced from ``ClientConfig.extra``:

* ``aws_region``            — AWS region, e.g. ``us-east-1`` (required)
* ``aws_access_key_id``     — AWS access key ID (optional; from credential chain)
* ``aws_secret_access_key`` — AWS secret access key (optional; from credential chain)
* ``aws_session_token``     — AWS session token for temporary credentials (optional)
* ``aws_profile``           — Named profile from ``~/.aws/credentials`` (optional)

Notes:
    ``boto3`` and ``botocore`` are optional dependencies.  An
    :class:`ImportError` is raised at construction time if they are absent.

    The Bedrock ``Converse`` API does not natively expose a server-sent event
    (SSE) streaming response over HTTP like OpenAI.  Streaming uses
    ``ConverseStream``, which returns an event-stream that ``botocore``
    processes asynchronously via ``aiobotocore`` if available, or
    synchronously via a thread-pool executor otherwise.

    Request mapping, response/stream parsing, error translation, and the
    shared daemon-thread transport live in the sibling ``_bedrock_*``
    modules.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from quadkit.ai.llm.clients._bedrock_errors import error_to_result
from quadkit.ai.llm.clients._bedrock_mappers import (
    bedrock_stream_chunks,
    parse_bedrock_response,
)
from quadkit.ai.llm.clients._bedrock_requests import (
    apply_thinking,
    build_converse_request,
    content_to_text,
)
from quadkit.ai.llm.clients._bedrock_transport import get_thread_pool
from quadkit.ai.llm.clients._tools_utils import parse_json_arguments
from quadkit.ai.llm.clients.base import AbstractLLMClient
from quadkit.ai.llm.exceptions import LLMError
from quadkit.ai.llm.multimodal.fetcher import fetch_image_as_base64
from quadkit.ai.llm.types import Completion, StreamChunk
from quadkit.contracts.ai.multimodal import (
    ImageBase64Part,
    ImageUrlPart,
    MessageContent,
    TextPart,
)
from quadkit.contracts.core import HealthCheckResult, HealthStatus
from quadkit.logging import (
    get_logger,
)
from quadkit.result import Ok, Result

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from quadkit.ai.llm.config import ClientConfig

logger = get_logger(__name__)

__all__ = ["BedrockClient"]


class BedrockClient(AbstractLLMClient):
    """AWS Bedrock client using the ``Converse`` API.

    Routes requests to the Bedrock ``converse`` (non-streaming) and
    ``converse_stream`` (streaming) endpoints.  The ``Converse`` API
    normalises request/response format across all Bedrock models, so
    no per-model message translation is needed.

    Args:
        config: LLM configuration.  ``config.extra`` must contain
            ``aws_region``.
    """

    def __init__(self, config: ClientConfig) -> None:
        """Initialise the Bedrock client.

        Args:
            config: LLM configuration with AWS-specific ``extra`` keys.

        Raises:
            ImportError: If ``boto3`` is not installed.
            ValueError: If ``aws_region`` is missing from ``config.extra``.
        """
        super().__init__(config=config)

        try:
            import boto3
        except ImportError as exc:
            raise ImportError(
                "BedrockClient requires 'boto3'. Install with: pip install boto3"
            ) from exc

        extra: dict[str, Any] = config.extra or {}
        region = extra.get("aws_region", "")
        if not region:
            raise ValueError(
                "BedrockClient requires 'aws_region' in ClientConfig.extra"
            )

        self._region = region
        boto_kwargs: dict[str, Any] = {"region_name": region}
        if extra.get("aws_access_key_id"):
            boto_kwargs["aws_access_key_id"] = extra["aws_access_key_id"]
        if extra.get("aws_secret_access_key"):
            boto_kwargs["aws_secret_access_key"] = extra["aws_secret_access_key"]
        if extra.get("aws_session_token"):
            boto_kwargs["aws_session_token"] = extra["aws_session_token"]
        if extra.get("aws_profile"):
            import boto3

            session = boto3.Session(profile_name=extra["aws_profile"], **boto_kwargs)
            self._client = session.client("bedrock-runtime")
        else:
            import boto3

            self._client = boto3.client("bedrock-runtime", **boto_kwargs)

    # ──────────────────────────────────────────────────────────────────
    # LLMClientProtocol implementation
    # ──────────────────────────────────────────────────────────────────

    async def _do_complete(
        self,
        messages: list[Any],
        *,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> Result[Completion, LLMError]:
        """Generate completion via Bedrock ``Converse``.

        Args:
            messages: OpenAI-compatible message list.
            model: Model ID override (Bedrock model ARN or ID).
            temperature: Sampling temperature.
            max_tokens: Maximum output tokens.
            **kwargs: Ignored for protocol compatibility.

        Returns:
            ``Ok(Completion)`` on success.  ``Err(LLMError)`` for recoverable
            failures.

        Raises:
            LLMAuthenticationError: On credential or authorisation failure.
            AIError: For unexpected infrastructure failures.
        """
        active_model = model or self.config.model
        bedrock_messages = await self._to_bedrock_messages_async(messages)
        tools = kwargs.pop("tools", None)
        request = build_converse_request(
            model=active_model,
            bedrock_messages=bedrock_messages,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            thinking=self.config.thinking,
            tools=tools,
        )

        try:
            raw = await asyncio.get_event_loop().run_in_executor(
                get_thread_pool(),
                lambda: self._client.converse(**request),
            )
        except Exception as exc:  # noqa: BLE001 - botocore raises dynamic provider exceptions
            return error_to_result(exc)

        return Ok(parse_bedrock_response(raw, active_model))

    async def _do_stream_chat(
        self,
        messages: list[Any],
        *,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> Result[AsyncIterator[StreamChunk], LLMError]:
        """Stream completion tokens from Bedrock ``ConverseStream``.

        Args:
            messages: OpenAI-compatible message list.
            model: Model ID override.
            temperature: Sampling temperature.
            max_tokens: Maximum output tokens.
            **kwargs: Ignored for protocol compatibility.

        Returns:
            ``Ok(AsyncIterator[StreamChunk])`` on success.
            ``Err(LLMError)`` for recoverable failures.

        Raises:
            LLMAuthenticationError: On credential or authorisation failure.
            AIError: For unexpected infrastructure failures.
        """
        active_model = model or self.config.model
        bedrock_messages = await self._to_bedrock_messages_async(messages)
        request = build_converse_request(
            model=active_model,
            bedrock_messages=bedrock_messages,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            thinking=self.config.thinking,
        )

        try:
            raw_stream = await asyncio.get_event_loop().run_in_executor(
                get_thread_pool(),
                lambda: self._client.converse_stream(**request),
            )
        except Exception as exc:  # noqa: BLE001 - botocore raises dynamic provider exceptions
            return error_to_result(exc)

        return Ok(bedrock_stream_chunks(raw_stream, active_model, get_thread_pool()))

    async def _do_chat(
        self,
        messages: list[Any],
        tools: list[Any] | None = None,
        *,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> Result[Completion, LLMError]:
        """Generate completion with optional tool calling on Bedrock.

        Tool calling is handled by :meth:`_do_complete` via
        ``complete(..., tools=...)``; this method forwards the tool
        descriptors to keep the ``chat`` code path consistent.

        Args:
            messages: OpenAI-compatible message list.
            tools: Optional tool descriptors.
            model: Model ID override.
            temperature: Sampling temperature.
            max_tokens: Maximum output tokens.
            **kwargs: Ignored for protocol compatibility.

        Returns:
            ``Ok(Completion)`` on success.  ``Err(LLMError)`` for recoverable
            failures.
        """
        return await self._do_complete(
            messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools,
            **kwargs,
        )

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Probe Bedrock by listing foundation models.

        Args:
            timeout: Informational only.

        Returns:
            Structured :class:`~quadkit.contracts.core.health.HealthCheckResult`.
        """
        try:
            import boto3

            mgmt = boto3.client("bedrock", region_name=self._region)
            await asyncio.get_event_loop().run_in_executor(
                get_thread_pool(),
                lambda: mgmt.list_foundation_models(maxResults=1),
            )
        except Exception as exc:  # noqa: BLE001 - boto3 exposes provider-specific exceptions
            return HealthCheckResult(
                component="llm.bedrock",
                status=HealthStatus.UNHEALTHY,
                error=f"Provider health check failed ({type(exc).__name__})",
            )

        return HealthCheckResult(
            component="llm.bedrock",
            status=HealthStatus.HEALTHY,
            details={"region": self._region, "model": self.config.model},
        )

    async def close(self) -> None:
        """Release the Bedrock boto3 client."""
        if self._client is not None:
            self._client.close()
            self._client = None
        await super().close()

    def _apply_thinking(self, request: dict[str, Any]) -> None:
        """Inject Bedrock extended-thinking parameters into the request payload.

        Delegates to :func:`~quadkit.ai.llm.clients._bedrock_requests.apply_thinking`.

        Args:
            request: Mutable Bedrock request dict.
        """
        apply_thinking(self.config.thinking, request)

    async def _build_content_blocks(
        self, content: MessageContent
    ) -> list[dict[str, Any]]:
        """Convert MessageContent to Bedrock ``Converse`` content blocks.

        Handles plain strings, TextPart, ImageBase64Part, and ImageUrlPart.
        ImageUrlPart entries are fetched and converted to base64 via
        ``fetch_image_as_base64``.

        Args:
            content: Message content (string or list of ContentPart).

        Returns:
            List of Bedrock content block dicts with wire format:
            - ``{"type": "text", "text": "..."}``.
            - ``{"type": "image", "source": {"type": "base64", "mediaType": "...", "data": "..."}}``
              (camelCase ``mediaType`` as per Bedrock API).

        Raises:
            LLMError: If image fetching fails (infrastructure error).
        """
        if isinstance(content, str):
            return [{"type": "text", "text": content}]

        blocks: list[dict[str, Any]] = []
        for part in content:
            if isinstance(part, TextPart):
                blocks.append({"type": "text", "text": part.text})
            elif isinstance(part, ImageBase64Part):
                blocks.append(
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "mediaType": part.media_type,
                            "data": part.data,
                        },
                    }
                )
            elif isinstance(part, ImageUrlPart):
                # Fetch and convert to base64
                fetched = await fetch_image_as_base64(part.url)
                blocks.append(
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "mediaType": fetched.media_type,
                            "data": fetched.data,
                        },
                    }
                )
        return blocks

    async def _to_bedrock_messages_async(
        self, messages: list[Any]
    ) -> list[dict[str, Any]]:
        """Async conversion of OpenAI-compatible messages to Bedrock format.

        System messages are excluded (handled separately). Multimodal content
        is converted using ``_build_content_blocks``.

        Args:
            messages: OpenAI-compatible message list (dicts or ChatMessage).

        Returns:
            List of Bedrock ``ConversationTurn`` dicts.
        """
        result: list[dict[str, Any]] = []
        for msg in messages:
            role = (
                msg.get("role", "user")
                if isinstance(msg, dict)
                else getattr(msg, "role", "user")
            )
            role_str = role.value if hasattr(role, "value") else str(role)
            if role_str == "system":
                continue

            content_raw = (
                msg.get("content", "")
                if isinstance(msg, dict)
                else getattr(msg, "content", "")
            )
            tool_calls = (
                msg.get("tool_calls")
                if isinstance(msg, dict)
                else getattr(msg, "tool_calls", None)
            )
            tool_call_id = (
                msg.get("tool_call_id", "")
                if isinstance(msg, dict)
                else getattr(msg, "tool_call_id", "")
            )

            # Tool results become user turns with a toolResult block
            if role_str == "tool":
                result.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "toolResult": {
                                    "toolUseId": tool_call_id,
                                    "content": [{"text": content_to_text(content_raw)}],
                                }
                            }
                        ],
                    }
                )
                continue

            # Use _build_content_blocks for content serialization
            bedrock_content = await self._build_content_blocks(content_raw)

            # Assistant turns that requested tools gain toolUse blocks
            if role_str == "assistant" and tool_calls:
                for call in tool_calls:
                    fn = getattr(call, "function", None)
                    if fn is None or not getattr(fn, "name", None):
                        continue
                    bedrock_content.append(
                        {
                            "toolUse": {
                                "toolUseId": getattr(call, "id", ""),
                                "name": fn.name,
                                "input": parse_json_arguments(fn.arguments),
                            }
                        }
                    )

            # Bedrock uses "user" and "assistant" roles only
            bedrock_role = "assistant" if role_str == "assistant" else "user"
            result.append({"role": bedrock_role, "content": bedrock_content})
        return result
