"""Audit bridge that emits audit entries per LLM completion (LXF-003)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, cast

from quadkit.contracts.ai.exceptions import LLMError
from quadkit.contracts.ai.llm import (
    ChatMessageProtocol,
    CompletionProtocol,
    LLMClientProtocol,
    StreamChunk,
)
from quadkit.contracts.audit import AuditEntry, AuditEventSeverity
from quadkit.contracts.infra import AsyncStream
from quadkit.result import Result

if TYPE_CHECKING:
    from quadkit.ai.llm.types import Completion
    from quadkit.contracts.audit import AuditLoggerProtocol
    from quadkit.primitives.context import Context

__all__ = ["LLMAuditBridge"]


class _AuditWrappedClient:
    """LLM client wrapper that emits audit entries on each completion.

    Lazily resolves the :class:`LLMAuditBridge` from the container on
    the first ``complete()`` call so it works during the DI registration
    phase when the bridge isn't resolvable yet.
    """

    def __init__(self, client: LLMClientProtocol, resolver: Any) -> None:
        self._client = client
        self._resolver = resolver
        self._bridge: LLMAuditBridge | None = None

    async def _get_bridge(self) -> LLMAuditBridge:
        if self._bridge is None:
            from quadkit.ai.llm.audit_bridge import LLMAuditBridge

            self._bridge = await self._resolver.resolve(LLMAuditBridge)
        return self._bridge

    async def complete(
        self,
        messages: Sequence[ChatMessageProtocol],
        **kwargs: Any,
    ) -> Result[CompletionProtocol, LLMError]:
        result = await self._client.complete(messages, **kwargs)
        if result.is_ok():
            try:
                bridge = await self._get_bridge()
                await bridge.on_completion(cast("Completion", result.unwrap()))
            except Exception:  # noqa: S110 — intentional best-effort fallback
                pass
        return result

    def stream_chat(
        self,
        messages: list[ChatMessageProtocol],
        **kwargs: Any,
    ) -> AsyncStream[StreamChunk, LLMError]:
        return self._client.stream_chat(messages, **kwargs)

    async def health_check(self, timeout: float = 5.0) -> Any:
        return await self._client.health_check(timeout=timeout)

    async def close(self) -> None:
        return await self._client.close()


class LLMAuditBridge:
    """Emits one ``AuditEntry`` per LLM completion.

    Wired via ``LLMModule.configure(audit_calls=True)``.  Default is ``False``
    to avoid noise for high-volume callers.
    """

    def __init__(self, audit_logger: AuditLoggerProtocol, ctx: Context) -> None:
        self._audit_logger = audit_logger
        self._ctx = ctx

    async def on_completion(self, completion: Completion) -> None:
        """Log an audit entry for a completed LLM call.

        Args:
            completion: The completed LLM response with provenance fields.
        """
        tenant_id = (
            self._ctx.get_tenant_id() if hasattr(self._ctx, "get_tenant_id") else None
        )
        correlation_id = (
            self._ctx.get_correlation_id()
            if hasattr(self._ctx, "get_correlation_id")
            else None
        )
        actor_id = (
            self._ctx.get_actor_id() if hasattr(self._ctx, "get_actor_id") else "system"
        )

        entry = AuditEntry(
            action="quadkit.llm.completion",
            actor_id=actor_id or "system",
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            command_payload_hash=completion.prompt_hash,
            payload_size_bytes=completion.prompt_tokens * 4
            if completion.prompt_tokens
            else None,
            severity=AuditEventSeverity.LOW,
            outcome="success",
            resource_type="llm.completion",
            resource_id=completion.request_id or "",
            metadata={
                "provider": completion.provider,
                "model": completion.model,
                "model_revision": completion.model_revision,
                "completion_tokens": completion.completion_tokens,
                "prompt_tokens": completion.prompt_tokens,
            },
        )
        await self._audit_logger.log(entry)

    @staticmethod
    def wrap(client: LLMClientProtocol, resolver: Any) -> LLMClientProtocol:
        """Wrap an LLM client to emit audit entries per completion.

        Args:
            client: The LLM client to wrap.
            resolver: Container or resolver used to lazily resolve
                ``LLMAuditBridge`` on first ``complete()`` call.

        Returns:
            A wrapped client that intercepts ``complete()`` to log
            audit entries via this bridge.
        """
        return _AuditWrappedClient(client, resolver)
