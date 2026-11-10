"""Tests for TokenCounterRegistry and token counter implementations."""

from __future__ import annotations

import pytest

from quadkit.ai.llm.pricing.registry import TokenCounterRegistry
from quadkit.ai.llm.pricing.tokens import (
    CharEstimateCounter,
    HuggingFaceCounter,
    MistralCounter,
    TiktokenCounter,
)
from quadkit.ai.llm.types import ChatMessage, Role


class TestTiktokenCounter:
    """Tests for TiktokenCounter."""

    def test_count_returns_positive_int(self, fake_tiktoken) -> None:
        """Test that count() returns a positive integer."""
        counter = TiktokenCounter(model="gpt-3.5-turbo")
        result = counter.count("Hello, world!")
        assert isinstance(result, int)
        assert result == len(fake_tiktoken.encode("Hello, world!"))
        assert result >= 1

    def test_count_messages_returns_positive_int(self, fake_tiktoken) -> None:
        """Test that count_messages() returns a positive integer."""
        counter = TiktokenCounter(model="gpt-4")
        messages = [
            ChatMessage(role=Role.USER, content="Hello!"),
            ChatMessage(role=Role.ASSISTANT, content="Hi there!"),
        ]
        result = counter.count_messages(messages)
        content_tokens = len(fake_tiktoken.encode("Hello!")) + len(
            fake_tiktoken.encode("Hi there!")
        )
        assert isinstance(result, int)
        assert result > content_tokens
        assert result >= 1

    def test_count_empty_text(self, fake_tiktoken) -> None:
        """Test counting empty text."""
        counter = TiktokenCounter()
        result = counter.count("")
        assert isinstance(result, int)
        assert result == len(fake_tiktoken.encode(""))
        assert result == 0

    def test_model_property(self) -> None:
        """Test model property returns correct model."""
        try:
            model = "gpt-4"
            counter = TiktokenCounter(model=model)
            assert counter.model == model
        except ImportError:
            pytest.skip("tiktoken not installed")


class TestCharEstimateCounter:
    """Tests for CharEstimateCounter."""

    def test_count_returns_positive_int(self) -> None:
        """Test that count() returns a positive integer."""
        counter = CharEstimateCounter()
        result = counter.count("Hello, world!")
        assert isinstance(result, int)
        assert result >= 1

    def test_count_messages_returns_positive_int(self) -> None:
        """Test that count_messages() returns a positive integer."""
        counter = CharEstimateCounter()
        messages = [
            ChatMessage(role=Role.USER, content="Hello!"),
            ChatMessage(role=Role.ASSISTANT, content="Hi there!"),
        ]
        result = counter.count_messages(messages)
        assert isinstance(result, int)
        assert result >= 1

    def test_count_empty_text(self) -> None:
        """Test counting empty text."""
        counter = CharEstimateCounter()
        result = counter.count("")
        assert isinstance(result, int)
        assert result >= 1

    def test_model_property(self) -> None:
        """Test model property returns correct model."""
        counter = CharEstimateCounter(model="test-model")
        assert counter.model == "test-model"


class TestHuggingFaceCounter:
    """Tests for HuggingFaceCounter."""

    def test_initialization(self) -> None:
        """Test HuggingFaceCounter initialization."""
        counter = HuggingFaceCounter()
        assert counter.model == "huggingface"

    def test_count_returns_positive_int(self) -> None:
        """Test that count() returns a positive integer."""
        counter = HuggingFaceCounter()
        result = counter.count("Hello, world!")
        assert isinstance(result, int)
        assert result >= 1

    def test_count_messages_returns_positive_int(self) -> None:
        """Test that count_messages() returns a positive integer."""
        counter = HuggingFaceCounter()
        messages = [
            ChatMessage(role=Role.USER, content="Hello!"),
            ChatMessage(role=Role.ASSISTANT, content="Hi there!"),
        ]
        result = counter.count_messages(messages)
        assert isinstance(result, int)
        assert result >= 1


class TestMistralCounter:
    """Tests for MistralCounter."""

    def test_initialization(self) -> None:
        """Test MistralCounter initialization."""
        counter = MistralCounter()
        assert counter.model == "mistral"

    def test_count_returns_positive_int(self) -> None:
        """Test that count() returns a positive integer."""
        counter = MistralCounter()
        result = counter.count("Hello, world!")
        assert isinstance(result, int)
        assert result >= 1

    def test_count_messages_returns_positive_int(self) -> None:
        """Test that count_messages() returns a positive integer."""
        counter = MistralCounter()
        messages = [
            ChatMessage(role=Role.USER, content="Hello!"),
            ChatMessage(role=Role.ASSISTANT, content="Hi there!"),
        ]
        result = counter.count_messages(messages)
        assert isinstance(result, int)
        assert result >= 1


class TestTokenCounterRegistry:
    """Tests for TokenCounterRegistry."""

    def test_with_defaults_returns_registry(self) -> None:
        """Test that with_defaults() returns a TokenCounterRegistry."""
        registry = TokenCounterRegistry.with_defaults()
        assert isinstance(registry, TokenCounterRegistry)

    def test_for_model_returns_counter_for_known_model(self) -> None:
        """Test that for_model() returns a counter for a known model."""
        registry = TokenCounterRegistry.with_defaults()
        counter = registry.for_model("gpt-3.5-turbo")
        assert counter is not None

    def test_for_model_returns_counter_for_unknown_model(self) -> None:
        """Test that for_model() returns a fallback counter for unknown models."""
        registry = TokenCounterRegistry.with_defaults()
        counter = registry.for_model("unknown-model-xyz")
        assert counter is not None
        assert isinstance(counter, CharEstimateCounter)

    def test_register_stores_counter(self) -> None:
        """Test that register() stores a counter backend."""
        registry = TokenCounterRegistry()
        counter = CharEstimateCounter(model="test-model")
        registry.register("char_estimate", counter)
        result = registry.for_model("test-model")
        # for_model tries patterns first, then falls back to char_estimate
        assert result is not None

    def test_map_models_pattern_matching(self) -> None:
        """Test that map_models() uses regex patterns."""
        registry = TokenCounterRegistry()
        counter = CharEstimateCounter()
        registry.register("base", counter)
        registry.map_models(r"test-.*", "base")
        assert registry.for_model("test-123") is counter
        assert registry.for_model("test-model") is counter

    def test_empty_registry_returns_default_counter(self) -> None:
        """Test that empty registry returns CharEstimateCounter for any model."""
        registry = TokenCounterRegistry()
        counter = registry.for_model("any-model")
        assert counter is not None
        assert isinstance(counter, CharEstimateCounter)

    def test_counter_count_works(self, fake_tiktoken) -> None:
        """Test that retrieved counter can count tokens."""
        registry = TokenCounterRegistry.with_defaults()
        counter = registry.for_model("gpt-4")
        result = counter.count("Hello, world!")
        assert isinstance(result, int)
        assert result == len(fake_tiktoken.encode("Hello, world!"))

    def test_counter_count_messages_works(self, fake_tiktoken) -> None:
        """Test that retrieved counter can count messages."""
        registry = TokenCounterRegistry.with_defaults()
        counter = registry.for_model("gpt-4")
        messages = [
            ChatMessage(role=Role.USER, content="Hello!"),
            ChatMessage(role=Role.ASSISTANT, content="Hi there!"),
        ]
        result = counter.count_messages(messages)
        content_tokens = len(fake_tiktoken.encode("Hello!")) + len(
            fake_tiktoken.encode("Hi there!")
        )
        assert isinstance(result, int)
        assert result > content_tokens

    def test_registry_resolves_tiktoken_for_gpt_models(self, fake_tiktoken) -> None:
        """for_model('gpt-4o') resolves to the tiktoken counter and counts."""
        registry = TokenCounterRegistry.with_defaults()
        counter = registry.for_model("gpt-4o")
        assert isinstance(counter, TiktokenCounter)
        assert counter.count("hello world") == len(fake_tiktoken.encode("hello world"))

    def test_registry_falls_back_to_char_estimate(self) -> None:
        """for_model('unknown-model-xyz') returns CharEstimateCounter fallback."""
        registry = TokenCounterRegistry.with_defaults()
        counter = registry.for_model("unknown-model-xyz-99999")
        assert isinstance(counter, CharEstimateCounter)

    def test_tiktoken_counter_exact_count(self) -> None:
        """TiktokenCounter.count() matches tiktoken's own encoder."""
        tiktoken = pytest.importorskip("tiktoken")
        try:
            enc = tiktoken.encoding_for_model("gpt-3.5-turbo")
        except OSError:
            # The encoding is downloaded on first use; an offline runner cannot.
            pytest.skip("tiktoken encoding requires a download")
        expected = len(enc.encode("Hello, world!"))
        counter = TiktokenCounter(model="gpt-3.5-turbo")
        assert counter.count("Hello, world!") == expected

    def test_char_estimate_counter_approximate(self) -> None:
        """CharEstimateCounter ~4 chars per token, within ±20% for typical text."""
        counter = CharEstimateCounter()
        text = "The quick brown fox jumps over the lazy dog"  # 43 chars → ~10-11 tokens
        result = counter.count(text)
        assert 8 <= result <= 13

    def test_count_messages_includes_overhead(self) -> None:
        """count_messages() returns more tokens than raw content sum alone."""
        counter = CharEstimateCounter()
        messages = [
            ChatMessage(role=Role.USER, content="Hi"),
            ChatMessage(role=Role.ASSISTANT, content="Hello"),
        ]
        content_only = sum(counter.count(str(m.content)) for m in messages)
        with_overhead = counter.count_messages(messages)
        assert with_overhead > content_only
