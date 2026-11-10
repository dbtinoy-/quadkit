"""LLM client wrappers — caching and provenance enrichment.

Both wrappers preserve the :class:`~quadkit.contracts.ai.llm.LLMClientProtocol`
shape (``complete`` / ``stream_chat`` / ``health_check`` / ``close``) so they
compose freely with each other and with :class:`LLMAuditBridge.wrap`.

Recommended layering (outer → inner)::

    LLMCacheWrapper(  # short-circuits cache hits before audit fires
        LLMAuditBridge.wrap(  # logs every real LLM call
            CompletionEnricher(  # fills provider / model_revision / prompt_hash
                provider_client
            )
        )
    )

The cache wrapper sits outermost so cache hits don't trigger audit log
entries (no real LLM call happened).  The enricher sits innermost so the
audit + cache layers see fully-populated :class:`Completion` provenance.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, cast

from quadkit.ai.llm.caching.types import build_llm_cache_key
from quadkit.contracts.ai.exceptions import LLMError
from quadkit.contracts.ai.llm import (
    ChatMessageProtocol,
    CompletionProtocol,
    LLMClientProtocol,
    StreamChunk,
)
from quadkit.contracts.infra import AsyncStream
from quadkit.logging import get_logger
from quadkit.result import Result
from quadkit.security.hashing import ambient as hashing

if TYPE_CHECKING:
    from quadkit.ai.llm.protocols import LLMCacheProtocol
    from quadkit.ai.llm.types import Completion

logger = get_logger(__name__)


def _hash_messages_for_cache_key(messages: Any) -> str:
    """Build a stable prompt string from ``messages`` for cache-key hashing.

    Accepts any iterable that yields chat-message-like objects.  Items may
    expose ``.role`` and ``.content`` attributes, or be plain dicts with
    those keys, or any other shape — they're stringified deterministically
    for hashing only.
    """
    parts: list[str] = []
    try:
        iterator = iter(messages)
    except TypeError:
        return str(messages)

    for msg in iterator:
        role = getattr(msg, "role", None)
        content = getattr(msg, "content", None)
        if role is None and isinstance(msg, dict):
            role = msg.get("role")
            content = msg.get("content")
        parts.append(f"{role}:{content}")
    return "|".join(parts)


def _compute_prompt_hash(messages: Any) -> bytes:
    """Compute a SHA-256 digest over the canonical message representation."""
    prompt = _hash_messages_for_cache_key(messages)
    return bytes.fromhex(hashing.hash_hex(prompt))


class _CacheWrappedClient:
    """Caches ``complete()`` results keyed by ``build_llm_cache_key``.

    Cache hits short-circuit before the wrapped client runs, so neither the
    underlying provider nor downstream wrappers (audit, etc.) see the call.
    """

    def __init__(
        self,
        client: LLMClientProtocol,
        cache: LLMCacheProtocol,
        provider: str,
        model: str,
        model_revision: str | None = None,
        ttl_seconds: float | None = None,
    ) -> None:
        self._client = client
        self._cache = cache
        self._provider = provider
        self._model = model
        self._model_revision = model_revision
        self._ttl_seconds = ttl_seconds

    def _key(self, messages: Any, kwargs: dict[str, Any]) -> str:
        prompt = _hash_messages_for_cache_key(messages)
        # Include kwargs in the prompt portion so different temperature /
        # max_tokens / tool sets produce distinct entries.
        kw_repr = ",".join(f"{k}={kwargs[k]}" for k in sorted(kwargs))
        prompt_with_kwargs = f"{prompt}::{kw_repr}" if kw_repr else prompt
        return build_llm_cache_key(
            provider=self._provider,
            model=self._model,
            prompt=prompt_with_kwargs,
            model_revision=self._model_revision,
            prompt_hash=_compute_prompt_hash(messages),
        )

    async def complete(
        self,
        messages: Sequence[ChatMessageProtocol],
        **kwargs: Any,
    ) -> Result[CompletionProtocol, LLMError]:
        key = self._key(messages, kwargs)
        cached = await self._cache.get(key)
        if cached is not None:
            logger.debug("llm_cache_hit")
            return cast("Result[CompletionProtocol, LLMError]", cached)

        result = await self._client.complete(messages, **kwargs)
        if result.is_ok():
            try:
                await self._cache.set(key, result, ttl=self._ttl_seconds)
            except Exception as exc:
                logger.warning(
                    "llm_cache_set_failed",
                    error_type=type(exc).__name__,
                )
        return result

    def stream_chat(
        self,
        messages: list[ChatMessageProtocol],
        **kwargs: Any,
    ) -> AsyncStream[StreamChunk, LLMError]:
        # Streaming is not cached — pass-through.
        return self._client.stream_chat(messages, **kwargs)

    async def health_check(self, timeout: float = 5.0) -> Any:
        return await self._client.health_check(timeout=timeout)

    async def close(self) -> None:
        return await self._client.close()


class LLMCacheWrapper:
    """Static factory namespace for the cache wrapper.

    Use :meth:`wrap` to attach a cache to a client.
    """

    @staticmethod
    def wrap(
        client: LLMClientProtocol,
        cache: LLMCacheProtocol,
        *,
        provider: str,
        model: str,
        model_revision: str | None = None,
        ttl_seconds: float | None = None,
    ) -> LLMClientProtocol:
        """Wrap *client* with a content-keyed cache.

        Args:
            client: The underlying LLM client.
            cache: Backing cache (must implement
                :class:`~quadkit.ai.llm.protocols.LLMCacheProtocol`).
            provider: Provider identifier (e.g. ``"anthropic"``).
            model: Model name (e.g. ``"claude-sonnet-4-6"``).
            model_revision: Optional pinned revision; participates in the key.
            ttl_seconds: Optional per-entry TTL; falls back to cache default.

        Returns:
            A wrapped client that short-circuits cache hits.
        """
        return _CacheWrappedClient(
            client=client,
            cache=cache,
            provider=provider,
            model=model,
            model_revision=model_revision,
            ttl_seconds=ttl_seconds,
        )

    @staticmethod
    def bind_cache(wrapped: LLMClientProtocol, cache: LLMCacheProtocol) -> None:
        """Late-bind the backing cache of a wrapped client.

        Used by ``LLMProvider.boot()``: the DI container is frozen between
        the register and boot phases, so a wrapper registered with a
        placeholder (``NoOpLLMCache``) at register time receives its real
        backend-backed cache here, without re-registering the container
        binding.

        Args:
            wrapped: A client previously returned by :meth:`wrap`.
            cache: The real cache to use from now on.

        Raises:
            TypeError: If *wrapped* is not a cache-wrapped client.
        """
        if not isinstance(wrapped, _CacheWrappedClient):
            msg = "bind_cache expects a client produced by LLMCacheWrapper.wrap"
            raise TypeError(msg)
        wrapped._cache = cache


class _EnrichedClient:
    """Fills missing provenance fields on returned :class:`Completion` objects.

    The provider clients populate ``model`` and ``content`` reliably; revision
    is only set when the response carries it.  This wrapper computes the
    ``prompt_hash`` from inputs and back-fills ``provider`` and
    ``model_revision`` from configuration when the underlying client did not
    set them.  Already-populated fields are never overwritten.
    """

    def __init__(
        self,
        client: LLMClientProtocol,
        provider: str,
        model: str,
        model_revision: str | None = None,
    ) -> None:
        self._client = client
        self._provider = provider
        self._model = model
        self._model_revision = model_revision

    def _enrich(self, completion: Completion, messages: Any) -> Completion:
        if not completion.provider:
            completion.provider = self._provider
        if not completion.model:
            completion.model = self._model
        if not completion.model_revision and self._model_revision:
            completion.model_revision = self._model_revision
        if completion.prompt_hash is None:
            completion.prompt_hash = _compute_prompt_hash(messages)
        return completion

    async def complete(
        self,
        messages: Sequence[ChatMessageProtocol],
        **kwargs: Any,
    ) -> Result[CompletionProtocol, LLMError]:
        result = await self._client.complete(messages, **kwargs)
        if result.is_ok():
            try:
                completion = result.unwrap()
                self._enrich(cast("Completion", completion), messages)
            except Exception as exc:
                logger.warning(
                    "completion_enrichment_failed",
                    error_type=type(exc).__name__,
                )
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


class CompletionEnricher:
    """Static factory namespace for the provenance-enrichment wrapper.

    Use :meth:`wrap` to attach enrichment to a client.
    """

    @staticmethod
    def wrap(
        client: LLMClientProtocol,
        *,
        provider: str,
        model: str,
        model_revision: str | None = None,
    ) -> LLMClientProtocol:
        """Wrap *client* so returned ``Completion`` objects carry provenance.

        Args:
            client: The underlying LLM client.
            provider: Provider name used to fill ``Completion.provider`` when
                the underlying client leaves it empty.
            model: Model name used to fill ``Completion.model`` when missing.
            model_revision: Pinned revision used to fill
                ``Completion.model_revision`` when the underlying client did
                not populate it from the response.

        Returns:
            A wrapped client that enriches successful completions in place.
        """
        return _EnrichedClient(
            client=client,
            provider=provider,
            model=model,
            model_revision=model_revision,
        )


__all__ = ["CompletionEnricher", "LLMCacheWrapper"]
