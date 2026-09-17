"""Routing protocols for multi-provider LLM inference.

Defines the protocol interfaces that decouple ``the optional provider``'s routing
implementation from consumers.  All types that live in extension packages
are represented as ``Any`` to satisfy the zero-dependency constraint of
``quadkit-contracts``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from datetime import datetime

__all__ = [
    "InferenceLoggerProtocol",
    "LLMRouterProtocol",
    "QuotaBackendProtocol",
    "RoutingStrategyProtocol",
]


@runtime_checkable
class RoutingStrategyProtocol(Protocol):
    """Protocol for routing strategies used by the LLM router."""

    async def execute(
        self,
        *,
        providers: list[Any],
        clients: dict[str, Any],
        quota: QuotaBackendProtocol,
        config: Any,
        messages: list[Any],
        kwargs: dict[str, Any],
    ) -> tuple[Any | None, list[str], int]:
        """Execute routing strategy."""
        ...


@runtime_checkable
class LLMRouterProtocol(Protocol):
    """Protocol for multi-provider LLM routing.

    Implementations cascade across a list of free providers (subject to
    daily quota tracking) before optionally falling through to a paid
    fallback.  Returns a ``Result[InferenceLog, InferenceError]`` —
    typed as ``Any`` here to avoid importing extension-package types.

    Example:
        ```python
        result = await router.route(
            messages=[{"role": "user", "content": "Hello!"}],
            temperature=0.2,
        )
        if result.is_ok():
            log = result.unwrap()
            print(log.completion.content)
        ```
    """

    async def route(
        self,
        messages: list[Any],
        **kwargs: Any,
    ) -> Any:
        """Route a completion request across configured providers.

        Args:
            messages: OpenAI-compatible message list.
            **kwargs: Provider-agnostic generation options (temperature,
                max_tokens, model, etc.).

        Returns:
            ``Result[InferenceLog, InferenceError]`` — ``Ok`` on any
            successful completion, ``Err`` when every provider (including
            the paid fallback) is exhausted or fails.
        """
        ...

    async def health_probe(self) -> Any:
        """Probe configured providers without issuing a normal inference request.

        Returns:
            ``Result[InferenceLog, InferenceError]`` — ``Ok`` on the first
            healthy configured provider, ``Err`` when no enabled provider can
            satisfy a lightweight health check.
        """
        ...


@runtime_checkable
class QuotaBackendProtocol(Protocol):
    """Protocol for per-provider daily quota tracking.

    Implementations MUST be safe for concurrent async access.  All
    mutations (increment, mark_exhausted, record_error) are fire-and-forget
    from the router's perspective; backends that persist to a database
    should absorb their own errors rather than propagating them.

    Example:
        ```python
        if await backend.is_exhausted("groq"):
            # Skip this provider
            ...
        await backend.increment("groq")
        ```
    """

    async def is_exhausted(self, provider: str) -> bool:
        """Return ``True`` when the provider has exceeded its daily quota.

        Args:
            provider: Provider name (e.g. ``"groq"``).

        Returns:
            ``True`` when the provider should be skipped.
        """
        ...

    async def increment(self, provider: str) -> None:
        """Record one successful completion for *provider* today.

        Args:
            provider: Provider name.
        """
        ...

    async def mark_exhausted(
        self, provider: str, *, until: datetime | None = None
    ) -> None:
        """Mark *provider* exhausted.

        Called when the provider returns HTTP 429 (transient throttle —
        pass a short ``until`` cooldown) or 402 (account-level — leave
        ``until`` unset).

        Args:
            provider: Cascade-entry key (``name:model``) or provider name.
            until: Exhaustion expiry.  ``None`` means the rest of the
                current UTC day (legacy behavior).
        """
        ...

    async def record_error(self, provider: str) -> None:
        """Record a non-exhaustion error for *provider*.

        Used for observability; does not affect quota state.

        Args:
            provider: Provider name.
        """
        ...

    async def get_usage(self, provider: str) -> Any:
        """Return today's usage record for *provider*.

        Args:
            provider: Provider name.

        Returns:
            ``ProviderUsage`` dataclass or ``None`` when no record exists.
        """
        ...

    async def get_all_usage(self) -> Any:
        """Return all today's usage records.

        Returns:
            ``list[ProviderUsage]`` for all tracked providers.
        """
        ...


@runtime_checkable
class InferenceLoggerProtocol(Protocol):
    """Protocol for recording inference attempt logs.

    Every routing run — successful or failed — should be logged for
    observability.  Implementations MUST NOT raise exceptions; logging
    failures are absorbed silently so they never interrupt inference.

    Example:
        ```python
        await logger.log(inference_log)
        recent = await logger.get_recent(limit=20)
        ```
    """

    async def log(self, entry: Any) -> None:
        """Record one ``InferenceLog`` entry.

        Args:
            entry: ``InferenceLog`` dataclass instance.
        """
        ...

    async def get_recent(self, limit: int = 100) -> list[Any]:
        """Return the most recent *limit* log entries.

        Args:
            limit: Maximum number of entries (newest-first).

        Returns:
            List of ``InferenceLog`` dataclass instances.
        """
        ...
