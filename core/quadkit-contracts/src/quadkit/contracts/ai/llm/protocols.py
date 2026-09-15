"""LLM client and prompt protocols."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from quadkit.contracts.ai.exceptions import ExtractionError, LLMError
from quadkit.contracts.ai.llm.types import ChatMessage, StreamChunk

if TYPE_CHECKING:
    from quadkit.contracts.core import HealthCheckResult
    from quadkit.contracts.core.result import Result
    from quadkit.contracts.infra import AsyncStream


@runtime_checkable
class ChatMessageProtocol(Protocol):
    """Structural protocol for chat message objects.

    Any object with ``role`` and ``content`` attributes satisfies this
    protocol.  Implemented concretely by ``quadkit.ai.llm.types.ChatMessage``.
    """

    @property
    def role(self) -> Any:
        """Message role (e.g. user, assistant, system)."""

    @property
    def content(self) -> Any:
        """Message content."""


@runtime_checkable
class CompletionProtocol(Protocol):
    """Structural protocol for LLM completion objects.

    Any object with ``content`` and ``model`` attributes satisfies this
    protocol.  Implemented concretely by ``quadkit.ai.llm.types.Completion``.
    """

    @property
    def content(self) -> str:
        """The generated completion text."""

    @property
    def model(self) -> str:
        """The model that produced this completion."""

    @property
    def thinking(self) -> Any | None:
        """Normalised thinking/reasoning output, or ``None`` when not enabled."""

    @property
    def usage(self) -> dict[str, int] | None:
        """Token usage statistics (prompt, completion, total tokens) or None."""


@runtime_checkable
class LLMClientProtocol(Protocol):
    """Protocol for LLM client implementations.

    All LLM providers (OpenAI, Anthropic, Google, etc.) should
    implement this interface.
    """

    async def complete(
        self,
        messages: Sequence[ChatMessageProtocol],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        tools: Sequence[Any] | None = None,
        stop_sequences: Sequence[str] | None = None,
        **kwargs: Any,
    ) -> Result[CompletionProtocol, LLMError]:
        """Generate a completion from messages.

        Args:
            messages: List of chat messages.
            model: Optional model override.
            temperature: Optional sampling temperature.
            max_tokens: Optional max output tokens.
            tools: Optional tool definitions.
            stop_sequences: Optional list of stop sequences for early termination.
            **kwargs: Provider-specific options.

        Returns:
            ``Ok(Completion)`` on success, ``Err(LLMError)`` on recoverable failure.
        """
        ...

    def stream_chat(
        self,
        messages: list[ChatMessageProtocol],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        tools: list[Any] | None = None,
        stop_sequences: list[str] | None = None,
        **kwargs: Any,
    ) -> AsyncStream[StreamChunk, LLMError]:
        """Start a streaming completion.

        This method returns an ``AsyncStream`` immediately (not wrapped in
        ``Result``). The stream is established lazily when iteration begins.
        Setup failures and mid-stream failures are both surfaced through the
        stream's typed error channel.

        Args:
            messages: List of chat messages.
            model: Optional model override.
            temperature: Optional sampling temperature.
            max_tokens: Optional max output tokens.
            tools: Optional tool definitions.
            stop_sequences: Optional list of stop sequences for early termination.
            **kwargs: Provider-specific options.

        Returns:
            ``AsyncStream[StreamChunk, LLMError]`` that yields chunks or
            surfaces typed errors through terminal operations (``collect()``,
            ``first()``, ``drain()``).
        """
        ...

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Perform a lightweight connectivity check.

        Returns:
            Structured health check result.
        """
        ...

    async def close(self) -> None:
        """Close the client and release resources."""
        ...


@runtime_checkable
class EmbeddingClientProtocol(Protocol):
    """Protocol for embedding client implementations."""

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for texts.

        Args:
            texts: List of strings to embed.

        Returns:
            List of embedding vectors.
        """
        ...

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Perform a lightweight connectivity check.

        Returns:
            Structured health check result.
        """
        ...

    async def close(self) -> None:
        """Close the client and release resources."""
        ...


@runtime_checkable
class StructuredExtractorProtocol(Protocol):
    """Protocol for extracting typed, validated data from LLM responses.

    Implementations wrap an ``LLMClientProtocol``, instruct the model to respond
    with JSON matching a given schema, and validate the parsed response
    against a target model type.
    """

    async def extract(
        self,
        prompt: str | list[ChatMessageProtocol],
        output_model: type[Any],
        *,
        max_retries: int = 2,
        model: str | None = None,
        **kwargs: Any,
    ) -> Result[Any, ExtractionError | LLMError]:
        """Extract structured data from an LLM response.

        Args:
            prompt: Text prompt or list of chat messages.
            output_model: Model class to validate the response against.
            max_retries: Number of additional attempts on parse/validation failure.
            model: Optional LLM model name override.
            **kwargs: Extra options forwarded to the underlying LLM client.

        Returns:
            ``Ok(output_model_instance)`` on success.
            ``Err(ExtractionError)`` on parse/validation failure.
            ``Err(LLMError)`` when the underlying client returns a recoverable
            provider/model failure.
        """
        ...


@runtime_checkable
class PromptTemplateProtocol(Protocol):
    """Protocol for prompt templates that render to text or chat messages."""

    @property
    def name(self) -> str:
        """Unique name identifying this template."""
        ...

    def render(self, **kwargs: Any) -> str | list[dict[str, str]]:
        """Render the template with the supplied variable values.

        Args:
            **kwargs: Variable name → value pairs.

        Returns:
            A plain string or a list of ``{"role": ..., "content": ...}`` dicts.
        """
        ...

    def get_variables(self) -> list[str]:
        """Return the list of declared variable names."""
        ...


@runtime_checkable
class PromptRegistryProtocol(Protocol):
    """Protocol for a named template registry."""

    def register(
        self,
        name: str,
        template: PromptTemplateProtocol,
        *,
        overwrite: bool = False,
    ) -> None:
        """Register a template under *name*."""
        ...

    def get(self, name: str) -> PromptTemplateProtocol:
        """Retrieve a template by name."""
        ...

    def list_names(self) -> list[str]:
        """Return all registered template names."""
        ...


@runtime_checkable
class TokenCounterProtocol(Protocol):
    """Model-aware token counter.

    Implementations use the exact tokenizer for the target model (tiktoken for
    OpenAI, AutoTokenizer for HuggingFace, mistral-common for Mistral). A
    character-estimate fallback is always available.

    Note: Methods are synchronous because tokenization is CPU-bound with no I/O.
    """

    def count(self, text: str) -> int:
        """Count tokens in a text string."""
        ...

    def count_messages(self, messages: Sequence[ChatMessageProtocol]) -> int:
        """Count tokens in a list of chat messages, including message overhead."""
        ...

    @property
    def model(self) -> str:
        """The model this counter is calibrated for."""
        ...


@runtime_checkable
class PromptAssemblerProtocol(Protocol):
    """Assembles prompt layers in cache-friendly static-to-dynamic order.

    The static-first ordering maximizes provider-side KV cache reuse. The
    assembler also injects provider-specific cache annotations (Anthropic's
    cache_control breakpoints, DeepSeek's 64-token padding, etc.).
    """

    def assemble(
        self,
        system: str,
        tools: list[Any] | None,
        reference_docs: list[str] | None,
        few_shot: list[ChatMessage] | None,
        history: list[ChatMessage],
        query: str,
        provider: str,
        dynamic_metadata: str | None = None,
    ) -> list[ChatMessage]:
        """Assemble a complete prompt message list.

        Args:
            system: System instructions (static, cached).
            tools: Tool/function definitions.
            reference_docs: Reference documents as text (semi-static).
            few_shot: Few-shot example messages (static, cached).
            history: Chat history messages (dynamic).
            query: Current user query (dynamic).
            provider: Provider name for cache annotation strategy.
            dynamic_metadata: Timestamps, user IDs, etc. (dynamic).

        Returns:
            Ordered list of ChatMessage instances ready for the LLM client.
        """
        ...


@runtime_checkable
class PromptRendererProtocol(Protocol):
    """Renders a prompt template with provided variables.

    Consumed by: quadkit-ai-prompt, quadkit-ai-rag.
    """

    def render(self, template: str, variables: dict[str, Any]) -> str:
        """Render a template string with the supplied variable mapping.

        Args:
            template: The raw template string.
            variables: Mapping of variable names to their values.

        Returns:
            The rendered prompt string.
        """
        ...


@runtime_checkable
class PromptOptimizerProtocol(Protocol):
    """Optimizes a rendered prompt for a specific model.

    Consumed by: quadkit-ai-prompt.
    """

    async def optimize(self, prompt: str, model: str, max_tokens: int) -> str:
        """Optimize a prompt for the target model and token budget.

        Args:
            prompt: The rendered prompt string to optimize.
            model: Target model identifier.
            max_tokens: Maximum token budget for the optimized prompt.

        Returns:
            The optimized prompt string.
        """
        ...


@runtime_checkable
class SemanticCacheProtocol(Protocol):
    """Embedding-based semantic similarity cache for LLM responses.

    Provides three-tier lookup: exact hash match (Tier 1), vector similarity
    match (Tier 2), and cache miss (caller invokes LLM).

    Placement note: Lives in ai/llm.py (not infra/cache/) because it carries
    AI-domain semantics (model tracking in store(), LLM response caching).
    """

    async def lookup(self, query: str) -> str | None:
        """Look up a query in the cache.

        Checks Tier 1 (exact hash) then Tier 2 (vector similarity).

        Args:
            query: The user query string.

        Returns:
            Cached response string, or ``None`` on cache miss.
        """
        ...

    async def store(self, query: str, response: str, model: str) -> None:
        """Store a query-response pair in both tiers.

        Args:
            query: The user query string.
            response: The LLM response to cache.
            model: The model that produced the response.
        """
        ...

    async def invalidate(self, query: str) -> bool:
        """Invalidate a cached entry by query.

        Args:
            query: The user query string to invalidate.

        Returns:
            ``True`` if the entry was found and removed, ``False`` otherwise.
        """
        ...


@runtime_checkable
class CostEstimatorProtocol(Protocol):
    """Estimates the monetary cost of LLM usage.

    Implementations map token usage for a model/provider to a cost in
    USD.  Consumed by agents (governance cost tracking) and any package
    that reports spend.  When no estimator is wired, callers must skip
    cost tracking rather than fabricate estimates.
    """

    def estimate_cost(
        self,
        model: str,
        total_tokens: int,
        provider: str | None = None,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
    ) -> float:
        """Estimate cost in USD for the given token usage.

        When *prompt_tokens* and *completion_tokens* are provided they are
        priced at the input and output rates respectively — this yields the
        most accurate estimate.  When both are ``0`` the caller has no
        usage split, so implementations must fall back to *total_tokens*
        using a documented approximation.

        Args:
            model: Model identifier (e.g. ``gpt-4o``).
            total_tokens: Total tokens consumed (prompt + completion).
            provider: Provider name (e.g. ``openai``) when pricing
                differs per provider.
            prompt_tokens: Input token count from ``Completion.usage``.
                Defaults to ``0`` (unknown).
            completion_tokens: Output token count from
                ``Completion.usage``.  Defaults to ``0`` (unknown).

        Returns:
            Estimated cost in USD.  Return ``0.0`` when pricing is
            unknown for the model.
        """
        ...
