"""Token counting and cost estimation utilities.

Example:
    >>> from quadkit.ai.llm import TiktokenCounter
    >>>
    >>> counter = TiktokenCounter(model="gpt-4")
    >>> tokens = counter.count("Hello, world!")
    >>> print(f"Tokens: {tokens}")

"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from quadkit.contracts.ai.llm import (
    ChatMessageProtocol,
)
from quadkit.domain import DomainModel
from quadkit.logging import (
    get_logger,
)
from quadkit.validation import Field

logger = get_logger(__name__)


@dataclass(init=False)
class TokenCount(DomainModel):
    """Token count result with metadata.

    Attributes:
        total: Total number of tokens.
        prompt_tokens: Number of tokens in the prompt.
        completion_tokens: Number of tokens in the completion (if applicable).
        model: Model name used for counting.
        timestamp: When the count was performed.

    """

    total: int = Field(..., description="Total token count")
    prompt_tokens: int = Field(default=0, description="Prompt token count")
    completion_tokens: int = Field(default=0, description="Completion token count")
    model: str = Field(..., description="Model used for counting")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Count timestamp",
    )


@dataclass(init=False)
class CostEstimate(DomainModel):
    """Cost estimation result.

    Attributes:
        prompt_cost: Cost for prompt tokens.
        completion_cost: Cost for completion tokens.
        total_cost: Total estimated cost.
        currency: Currency code (default: USD).
        model: Model name.
        rate_per_1k_prompt: Rate per 1000 prompt tokens.
        rate_per_1k_completion: Rate per 1000 completion tokens.

    """

    prompt_cost: float = Field(..., description="Prompt token cost")
    completion_cost: float = Field(..., description="Completion token cost")
    total_cost: float = Field(..., description="Total cost")
    currency: str = Field(default="USD", description="Currency code")
    model: str = Field(..., description="Model name")
    rate_per_1k_prompt: float = Field(..., description="Rate per 1k prompt tokens")
    rate_per_1k_completion: float = Field(
        ...,
        description="Rate per 1k completion tokens",
    )


class TiktokenCounter:
    """Token counter using tiktoken (OpenAI/compatible models).

    Implements TokenCounterProtocol using tiktoken for precise counting.
    tiktoken is a required dependency for this counter.

    Args:
        model: Model name (e.g. 'gpt-4', 'gpt-3.5-turbo').
        encoding_name: Optional tiktoken encoding name override.
    """

    def __init__(
        self,
        model: str = "gpt-3.5-turbo",
        encoding_name: str | None = None,
    ) -> None:
        """Initialize TiktokenCounter.

        Args:
            model: Model name for token counting.
            encoding_name: Optional tiktoken encoding name override.

        Raises:
            ImportError: If tiktoken is not installed.
        """
        import tiktoken

        self._model = model
        self._encoding_name = encoding_name
        self._encoder: Any | None = None
        self._tiktoken = tiktoken

    @property
    def model(self) -> str:
        """The model this counter is calibrated for."""
        return self._model

    def _get_encoder(self) -> Any:
        """Get tiktoken encoder lazily."""
        if self._encoder is None:
            try:
                if self._encoding_name:
                    self._encoder = self._tiktoken.get_encoding(self._encoding_name)
                else:
                    self._encoder = self._tiktoken.encoding_for_model(self._model)
            except (KeyError, ValueError):
                self._encoder = self._tiktoken.get_encoding("cl100k_base")
        return self._encoder

    def count(self, text: str) -> int:
        """Count tokens in a text string."""
        encoder = self._get_encoder()
        return len(encoder.encode(text))

    def count_messages(self, messages: Sequence[ChatMessageProtocol]) -> int:
        """Count tokens in a list of chat messages, including overhead."""
        encoder = self._get_encoder()
        tokens_per_message = 3
        tokens_per_name = 1
        num_tokens = 0
        for msg in messages:
            num_tokens += tokens_per_message
            num_tokens += len(encoder.encode(str(msg.content or "")))
            if hasattr(msg, "role"):
                num_tokens += len(encoder.encode(str(msg.role)))
            if hasattr(msg, "name") and msg.name:
                num_tokens += tokens_per_name
        num_tokens += 3
        return num_tokens


class HuggingFaceCounter:
    """Token counter using HuggingFace AutoTokenizer (lazy-loaded).

    When constructed without a model, uses character estimation (~4 chars/token).
    When constructed with a model name, lazy-loads that model's tokenizer on first use.

    Args:
        model: Optional HuggingFace model name. If None, uses char estimation fallback.
    """

    def __init__(self, model: str | None = None) -> None:
        """Initialize HuggingFaceCounter.

        Args:
            model: Optional HuggingFace model name for tokenizer loading.
        """
        self._model = model
        self._tokenizer: Any | None = None
        self._loaded: bool = False

    @property
    def model(self) -> str:
        """Backend identifier."""
        return self._model or "huggingface"

    def _get_tokenizer(self) -> Any | None:
        """Lazily load tokenizer on first use."""
        if self._model is None:
            return None  # Use char estimation
        if not self._loaded:
            self._loaded = True
            try:
                from transformers import AutoTokenizer

                self._tokenizer = AutoTokenizer.from_pretrained(
                    self._model,
                    use_fast=True,
                )
            except ImportError as e:
                logger.warning(
                    "huggingface_counter_import_failed", error_type=type(e).__name__
                )
            except OSError as e:
                logger.warning(
                    "huggingface_counter_load_failed",
                    error_type=type(e).__name__,
                )
        return self._tokenizer

    def count(self, text: str) -> int:
        """Count tokens in a text string."""
        tok = self._get_tokenizer()
        if tok is None:
            return max(1, len(text) // 4)
        return len(tok.encode(text))

    def count_messages(self, messages: Sequence[ChatMessageProtocol]) -> int:
        """Count tokens in a list of chat messages."""
        return (
            sum(self.count(str(m.content or "")) for m in messages) + len(messages) * 4
        )


class MistralCounter:
    """Token counter using mistral-common tokenizer (lazy-loaded).

    Tokenizer is loaded on first use, not at construction time.
    """

    def __init__(self) -> None:
        """Initialize MistralCounter."""
        self._tokenizer: Any | None = None
        self._loaded: bool = False

    @property
    def model(self) -> str:
        """Backend identifier."""
        return "mistral"

    def _get_tokenizer(self) -> Any | None:
        """Lazily load tokenizer on first use."""
        if not self._loaded:
            self._loaded = True
            try:
                from mistral_common.tokens.tokenizers.mistral import (
                    MistralTokenizer,
                )

                self._tokenizer = MistralTokenizer.v3()
            except ImportError as e:
                logger.warning(
                    "mistral_counter_import_failed", error_type=type(e).__name__
                )
            except Exception as e:  # noqa: BLE001 — tokenizer init raises varied errors (OS, network, parse)
                logger.warning(
                    "mistral_counter_load_failed", error_type=type(e).__name__
                )
        return self._tokenizer

    def count(self, text: str) -> int:
        """Count tokens in a text string."""
        tok = self._get_tokenizer()
        if tok is None:
            return max(1, len(text) // 4)
        try:
            # Try the instruct_tokenizer path (mistral-common v1+)
            encoded = tok.instruct_tokenizer.tokenizer.encode(
                text, bos=False, eos=False
            )
            return len(encoded)
        except AttributeError:
            # Fallback: try direct encode (older API or alternate path)
            try:
                return len(tok.encode(text))
            except AttributeError:
                return max(1, len(text) // 4)

    def count_messages(self, messages: Sequence[ChatMessageProtocol]) -> int:
        """Count tokens in a list of chat messages."""
        return (
            sum(self.count(str(m.content or "")) for m in messages) + len(messages) * 4
        )


class CharEstimateCounter:
    """Character-based token count estimator (~4 chars per token).

    Always available without any optional dependencies.
    Suitable as a safe fallback counter.

    Args:
        model: Model name (used for identification only).
    """

    def __init__(self, model: str = "unknown") -> None:
        """Initialize CharEstimateCounter.

        Args:
            model: Model name for identification.
        """
        self._model = model

    @property
    def model(self) -> str:
        """The model this counter is calibrated for."""
        return self._model

    def count(self, text: str) -> int:
        """Count tokens using character estimation."""
        return max(1, len(text) // 4)

    def count_messages(self, messages: Sequence[ChatMessageProtocol]) -> int:
        """Count tokens in a list of chat messages."""
        return (
            sum(self.count(str(m.content or "")) for m in messages) + len(messages) * 4
        )


def create_token_counter(
    model: str = "gpt-3.5-turbo",
    encoding_name: str | None = None,
) -> TiktokenCounter:
    """Factory function for creating token counters.

    Args:
        model: Model name.
        encoding_name: Optional encoding name override.

    Returns:
        TiktokenCounter instance.

    Example:
        >>> from quadkit.ai.llm import create_token_counter
        >>>
        >>> counter = create_token_counter("gpt-4")
        >>> count = counter.count("Hello!")
        >>> print(count)

    """
    return TiktokenCounter(
        model=model,
        encoding_name=encoding_name,
    )
