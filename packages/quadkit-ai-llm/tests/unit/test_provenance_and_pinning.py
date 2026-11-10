"""Tests for LLM provenance tracking and model pinning (LXF-003)."""

from __future__ import annotations

from dataclasses import replace

import pytest

from quadkit.ai.llm.exceptions import ModelRevisionMismatchError


class TestModelPinPolicy:
    """Tests for ModelPinPolicy enum."""

    def test_enum_values(self) -> None:
        from quadkit.ai.llm.pinning import ModelPinPolicy
        assert ModelPinPolicy.EXACT.value == "exact"
        assert ModelPinPolicy.LATEST_MINOR.value == "latest_minor"
        assert ModelPinPolicy.LATEST.value == "latest"

    def test_default_is_latest(self) -> None:
        from quadkit.ai.llm.pinning import ModelPinPolicy
        assert ModelPinPolicy.LATEST == "latest"


class TestClientConfigModelRevision:
    """Tests for ClientConfig model_revision and pin_policy."""

    def test_model_revision_defaults_to_none(self) -> None:
        from quadkit.ai.llm.config import ClientConfig
        config = ClientConfig(enabled=False)
        assert config.model_revision is None

    def test_pin_policy_defaults_to_latest(self) -> None:
        from quadkit.ai.llm.config import ClientConfig
        from quadkit.ai.llm.pinning import ModelPinPolicy
        config = ClientConfig(enabled=False)
        assert config.pin_policy == ModelPinPolicy.LATEST

    def test_model_revision_accepts_value(self) -> None:
        from quadkit.ai.llm.config import ClientConfig
        config = ClientConfig(enabled=False, model_revision="2026-01-01")
        assert config.model_revision == "2026-01-01"

    def test_pin_policy_accepts_exact(self) -> None:
        from quadkit.ai.llm.config import ClientConfig
        from quadkit.ai.llm.pinning import ModelPinPolicy
        config = ClientConfig(enabled=False, pin_policy=ModelPinPolicy.EXACT)
        assert config.pin_policy == ModelPinPolicy.EXACT


class TestEnforcePinPolicy:
    """Tests for pin policy enforcement."""

    def test_exact_match_passes(self) -> None:
        from quadkit.ai.llm.pinning import enforce_pin_policy, ModelPinPolicy
        enforce_pin_policy("rev-1", "rev-1", ModelPinPolicy.EXACT)  # no raise

    def test_exact_mismatch_raises(self) -> None:
        from quadkit.ai.llm.pinning import enforce_pin_policy, ModelPinPolicy
        with pytest.raises(ModelRevisionMismatchError):
            enforce_pin_policy("rev-1", "rev-2", ModelPinPolicy.EXACT)

    def test_latest_accepts_any(self) -> None:
        from quadkit.ai.llm.pinning import enforce_pin_policy, ModelPinPolicy
        enforce_pin_policy(None, "rev-anything", ModelPinPolicy.LATEST)  # no raise

    def test_latest_minor_accepts_same_major(self) -> None:
        from quadkit.ai.llm.pinning import enforce_pin_policy, ModelPinPolicy
        # "2026-01" and "2026-02" share the major prefix "2026"
        enforce_pin_policy("2026-01", "2026-02", ModelPinPolicy.LATEST_MINOR)  # no raise

    def test_latest_minor_rejects_different_major(self) -> None:
        from quadkit.ai.llm.pinning import enforce_pin_policy, ModelPinPolicy
        with pytest.raises(ModelRevisionMismatchError):
            enforce_pin_policy("2026-01", "2025-12", ModelPinPolicy.LATEST_MINOR)

    def test_error_message_contains_details(self) -> None:
        from quadkit.ai.llm.pinning import enforce_pin_policy, ModelPinPolicy
        try:
            enforce_pin_policy("rev-a", "rev-b", ModelPinPolicy.EXACT)
        except ModelRevisionMismatchError as e:
            msg = str(e)
            assert "rev-a" in msg
            assert "rev-b" in msg
            assert "EXACT" in msg


class TestCompletionProvenance:
    """Tests for Completion provenance fields."""

    def test_completion_has_provenance_fields(self) -> None:
        from quadkit.ai.llm.types import Completion
        completion = Completion(
            content="Hello",
            model="gpt-4",
            provider="openai",
            model_revision="2026-01-01",
            prompt_hash=b"abcdef1234567890",
            completion_tokens=50,
            prompt_tokens=100,
            request_id="req-123",
        )
        assert completion.provider == "openai"
        assert completion.model_revision == "2026-01-01"
        assert completion.prompt_hash == b"abcdef1234567890"
        assert completion.completion_tokens == 50
        assert completion.prompt_tokens == 100
        assert completion.request_id == "req-123"

    def test_completion_provenance_defaults(self) -> None:
        from quadkit.ai.llm.types import Completion
        completion = Completion(content="Hello", model="gpt-4")
        assert completion.provider == ""
        assert completion.model_revision == ""
        assert completion.prompt_hash is None
        assert completion.completion_tokens == 0
        assert completion.prompt_tokens == 0
        assert completion.request_id is None


class TestBuildLLMCacheKey:
    """Tests for cache key building with provenance."""

    def test_cache_key_includes_provider_model_prompt(self) -> None:
        from quadkit.ai.llm.caching.types import build_llm_cache_key
        key = build_llm_cache_key(provider="openai", model="gpt-4", prompt="hello")
        assert isinstance(key, str)
        assert len(key) == 64

    def test_cache_key_differs_with_revision(self) -> None:
        from quadkit.ai.llm.caching.types import build_llm_cache_key
        k1 = build_llm_cache_key("openai", "gpt-4", "hello", model_revision="v1")
        k2 = build_llm_cache_key("openai", "gpt-4", "hello", model_revision="v2")
        assert k1 != k2

    def test_cache_key_differs_with_prompt_hash(self) -> None:
        from quadkit.ai.llm.caching.types import build_llm_cache_key
        k1 = build_llm_cache_key("openai", "gpt-4", "hello", prompt_hash=b"hash1")
        k2 = build_llm_cache_key("openai", "gpt-4", "hello", prompt_hash=b"hash2")
        assert k1 != k2

    def test_cache_key_same_without_revision_and_hash(self) -> None:
        from quadkit.ai.llm.caching.types import build_llm_cache_key
        k1 = build_llm_cache_key("openai", "gpt-4", "hello")
        k2 = build_llm_cache_key("openai", "gpt-4", "hello")
        assert k1 == k2

    def test_cache_key_same_prompt_revision_hit(self) -> None:
        from quadkit.ai.llm.caching.types import build_llm_cache_key
        k1 = build_llm_cache_key("openai", "gpt-4", "hello", model_revision="v1", prompt_hash=b"abc")
        k2 = build_llm_cache_key("openai", "gpt-4", "hello", model_revision="v1", prompt_hash=b"abc")
        assert k1 == k2


class TestModelRevisionMismatchError:
    """Tests for ModelRevisionMismatchError exception."""

    def test_is_llm_error(self) -> None:
        from quadkit.ai.llm.exceptions import LLMError, ModelRevisionMismatchError
        assert issubclass(ModelRevisionMismatchError, LLMError)

    def test_error_code_present(self) -> None:
        from quadkit.ai.llm.exceptions import ModelRevisionMismatchError
        err = ModelRevisionMismatchError("expected rev-a, got rev-b")
        assert hasattr(err, "_code")
