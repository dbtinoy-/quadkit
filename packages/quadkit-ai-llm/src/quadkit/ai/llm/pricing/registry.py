"""Token counter registry for managing model-to-counter mappings."""

from __future__ import annotations

import re

from quadkit.contracts.ai.llm import TokenCounterProtocol
from quadkit.logging import (
    get_logger,
)

logger = get_logger(__name__)


def _tiktoken_available() -> bool:
    """Check if tiktoken is installed."""
    try:
        import tiktoken  # noqa: F401

        return True
    except ImportError:
        return False


def _transformers_available() -> bool:
    """Check if HuggingFace transformers is installed."""
    try:
        import transformers  # noqa: F401

        return True
    except ImportError:
        return False


def _mistral_available() -> bool:
    """Check if mistral-common is installed."""
    try:
        import mistral_common  # noqa: F401

        return True
    except ImportError:
        return False


class TokenCounterRegistry:
    """Registry mapping model-name patterns to TokenCounterProtocol backends.

    Uses named backend keys and regex patterns for flexible model mapping.

    Usage::

        registry = TokenCounterRegistry.with_defaults()
        counter = registry.for_model("gpt-4o")
        tokens = counter.count("Hello!")
    """

    def __init__(self) -> None:
        """Create an empty registry."""
        self._backends: dict[str, TokenCounterProtocol] = {}
        self._patterns: list[tuple[re.Pattern[str], str]] = []

    @classmethod
    def _default_entries(
        cls,
    ) -> dict[str, TokenCounterProtocol]:
        """Declare the available token counter backends.

        char_estimate is always available; tiktoken/huggingface/mistral are
        included only when their optional dependencies are installed.
        """
        from quadkit.ai.llm.pricing.tokens import CharEstimateCounter

        entries: dict[str, TokenCounterProtocol] = {
            "char_estimate": CharEstimateCounter(),
        }
        if _tiktoken_available():
            from quadkit.ai.llm.pricing.tokens import TiktokenCounter

            entries["tiktoken"] = TiktokenCounter()
        if _transformers_available():
            from quadkit.ai.llm.pricing.tokens import HuggingFaceCounter

            entries["huggingface"] = HuggingFaceCounter()
        if _mistral_available():
            from quadkit.ai.llm.pricing.tokens import MistralCounter

            entries["mistral"] = MistralCounter()
        return entries

    @classmethod
    def with_defaults(cls) -> TokenCounterRegistry:
        """Create registry with all available tokenizer backends.

        Registers every backend declared by :meth:`_default_entries` and
        maps the model families each backend serves.
        """
        registry = cls()
        declared = cls._default_entries()
        for key, counter in declared.items():
            registry.register(key, counter)

        if "tiktoken" in declared:
            registry.map_models(r"gpt-.*|o[0-9].*|text-embedding-.*", "tiktoken")
            logger.debug("token_counter_registry_tiktoken_registered")
        else:
            logger.warning(
                "token_counter_registry_tiktoken_unavailable",
                fallback="char_estimate",
            )

        if "huggingface" in declared:
            registry.map_models(
                r"llama-.*|qwen-.*|deepseek-.*|gemma-.*",
                "huggingface",
            )
            logger.debug("token_counter_registry_huggingface_registered")

        if "mistral" in declared:
            registry.map_models(r"mistral-.*|codestral-.*", "mistral")
            logger.debug("token_counter_registry_mistral_registered")

        return registry

    def register(self, key: str, counter: TokenCounterProtocol) -> None:
        """Register a counter backend under a named key.

        Args:
            key: Backend name (e.g., 'tiktoken', 'huggingface', 'char_estimate').
            counter: Counter implementing TokenCounterProtocol.
        """
        self._backends[key] = counter

    def map_models(self, pattern: str, counter_key: str) -> None:
        """Map a regex pattern of model names to a backend key.

        Args:
            pattern: Regex pattern matching model names (case-insensitive).
            counter_key: Backend key (must be registered).
        """
        if counter_key not in self._backends:
            logger.warning("token_counter_map_key_not_found")
            return
        self._patterns.append((re.compile(pattern, re.IGNORECASE), counter_key))

    def for_model(self, model: str) -> TokenCounterProtocol:
        """Get the best counter for the given model name.

        Tries exact regex match in _patterns first, falls back to 'char_estimate'.

        Args:
            model: Model name.

        Returns:
            TokenCounterProtocol implementation.
        """
        for compiled_pattern, key in self._patterns:
            if compiled_pattern.match(model):
                return self._backends[key]
        if "char_estimate" in self._backends:
            return self._backends["char_estimate"]
        from quadkit.ai.llm.pricing.tokens import CharEstimateCounter

        return CharEstimateCounter()
