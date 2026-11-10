"""Unit tests for capability-based routing (P5.3).

Tests LLMRouter._filter_by_capabilities() and its integration with
ModelSelector to filter providers by required model capabilities.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.ai.llm.routing.backends.memory import InMemoryQuotaBackend
from quadkit.ai.llm.routing.config import (
    GenerationDefaults,
    LLMConfig,
    ProviderConfig,
)
from quadkit.ai.llm.routing.loggers.memory import InMemoryInferenceLogger
from quadkit.ai.llm.routing.router import LLMRouter
from quadkit.ai.llm.selection.core import ModelCapabilities, ModelSelector
from quadkit.ai.llm.types import Completion, TokenUsage
from quadkit.result import Ok, Err


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_completion(text: str = "ok") -> Completion:
    return Completion(
        content=text,
        model="test-model",
        usage=TokenUsage(prompt_tokens=5, completion_tokens=10, total_tokens=15),
    )


def _make_client(text: str = "ok"):
    client = MagicMock()
    client.complete = AsyncMock(return_value=Ok(_make_completion(text=text)))
    return client


def _make_config(providers: list[ProviderConfig]) -> LLMConfig:
    return LLMConfig(
        providers=providers,
        defaults=GenerationDefaults(temperature=0.2),
    )


def _make_provider_cfg(name: str, primary: str) -> ProviderConfig:
    return ProviderConfig(
        name=name,
        model=primary,
        api_key="fake-key",
    )


def _make_router(
    clients: dict,
    config: LLMConfig,
    model_selector: ModelSelector | None = None,
) -> LLMRouter:
    return LLMRouter(
        clients=clients,
        quota_backend=InMemoryQuotaBackend(),
        inference_logger=InMemoryInferenceLogger(),
        config=config,
        model_selector=model_selector,
    )


def _make_vision_selector() -> ModelSelector:
    """Selector with two models: one with vision, one without."""
    capabilities = {
        "vision-model": ModelCapabilities(
            max_tokens=64000,
            supports_functions=True,
            supports_vision=True,
        ),
        "text-only-model": ModelCapabilities(
            max_tokens=16000,
            supports_functions=True,
            supports_vision=False,
        ),
    }
    return ModelSelector(
        default_model="text-only-model",
        model_capabilities=capabilities,
    )


# ---------------------------------------------------------------------------
# No-op when no capabilities required
# ---------------------------------------------------------------------------


class TestCapabilityFilterNoOp:
    @pytest.mark.asyncio
    async def test_all_providers_kept_when_no_capability_filter(self):
        """Without required_capabilities kwarg, all providers are tried."""
        vision = _make_client("from-vision")
        text = _make_client("from-text")

        selector = _make_vision_selector()
        config = _make_config([
            _make_provider_cfg("openai", "vision-model"),
            _make_provider_cfg("groq", "text-only-model"),
        ])
        router = _make_router(
            {"openai:vision-model": vision, "groq:text-only-model": text},
            config,
            model_selector=selector,
        )

        # No required_capabilities — should succeed with first provider
        result = await router.route([{"role": "user", "content": "hello"}])

        assert result.is_ok()

    @pytest.mark.asyncio
    async def test_all_providers_kept_when_no_selector_configured(self):
        """Without a ModelSelector, capability filtering is a no-op."""
        client = _make_client("hello")

        config = _make_config([_make_provider_cfg("openai", "vision-model")])
        # No model_selector passed
        router = _make_router({"openai:vision-model": client}, config)

        result = await router.route(
            [{"role": "user", "content": "analyze image"}],
            required_capabilities=["supports_vision"],
        )

        assert result.is_ok()


# ---------------------------------------------------------------------------
# Capability filtering removes incapable providers
# ---------------------------------------------------------------------------


class TestCapabilityFilterRemovesIncapableProviders:
    @pytest.mark.asyncio
    async def test_vision_only_request_skips_text_only_provider(self):
        """Provider with text-only model is skipped for vision requests."""
        vision_client = _make_client("seen it")
        text_client = _make_client("cant see")

        selector = _make_vision_selector()
        config = _make_config([
            _make_provider_cfg("openai", "vision-model"),
            _make_provider_cfg("groq", "text-only-model"),
        ])
        router = _make_router(
            {"openai:vision-model": vision_client, "groq:text-only-model": text_client},
            config,
            model_selector=selector,
        )

        result = await router.route(
            [{"role": "user", "content": "describe the image"}],
            required_capabilities=["supports_vision"],
        )

        assert result.is_ok()
        # Only the vision-capable provider should have been called
        vision_client.complete.assert_called_once()
        text_client.complete.assert_not_called()

    @pytest.mark.asyncio
    async def test_functions_required_skips_functions_unsupported_model(self):
        """Provider with function-unsupported model is removed from routing."""
        functions_capable = _make_client("tool result")
        no_functions = _make_client("no tools")

        capabilities = {
            "gpt-4-turbo": ModelCapabilities(
                max_tokens=128000,
                supports_functions=True,
                supports_vision=False,
            ),
            "ollama/llama3": ModelCapabilities(
                max_tokens=8192,
                supports_functions=False,
                supports_vision=False,
            ),
        }
        selector = ModelSelector(default_model="gpt-4-turbo", model_capabilities=capabilities)
        config = _make_config([
            _make_provider_cfg("openai", "gpt-4-turbo"),
            _make_provider_cfg("ollama", "ollama/llama3"),
        ])
        router = _make_router(
            {"openai:gpt-4-turbo": functions_capable, "ollama:ollama/llama3": no_functions},
            config,
            model_selector=selector,
        )

        result = await router.route(
            [{"role": "user", "content": "call a tool"}],
            required_capabilities=["supports_functions"],
        )

        assert result.is_ok()
        functions_capable.complete.assert_called_once()
        no_functions.complete.assert_not_called()


# ---------------------------------------------------------------------------
# Fail-open: unknown model kept in provider list
# ---------------------------------------------------------------------------


class TestCapabilityFilterFailOpen:
    @pytest.mark.asyncio
    async def test_unknown_model_kept_in_list_fail_open(self):
        """Providers with models unknown to the selector are kept (fail-open)."""
        custom_client = _make_client("custom result")

        capabilities = {
            "known-model": ModelCapabilities(
                max_tokens=8192,
                supports_functions=False,
                supports_vision=False,
            ),
        }
        selector = ModelSelector(default_model="known-model", model_capabilities=capabilities)
        config = _make_config([
            # "my-custom-model" is not in the selector's capabilities dict
            _make_provider_cfg("custom", "my-custom-model"),
        ])
        router = _make_router(
            {"custom:my-custom-model": custom_client},
            config,
            model_selector=selector,
        )

        result = await router.route(
            [{"role": "user", "content": "hello"}],
            required_capabilities=["supports_vision"],
        )

        assert result.is_ok()
        custom_client.complete.assert_called_once()

    @pytest.mark.asyncio
    async def test_fallback_to_all_providers_when_all_filtered_out(self):
        """If filtering removes all providers, falls back to full list."""
        text_client = _make_client("best effort")

        capabilities = {
            "text-only-model": ModelCapabilities(
                max_tokens=8192,
                supports_functions=False,
                supports_vision=False,
            ),
        }
        selector = ModelSelector(
            default_model="text-only-model", model_capabilities=capabilities
        )
        config = _make_config([
            _make_provider_cfg("groq", "text-only-model"),
        ])
        router = _make_router(
            {"groq:text-only-model": text_client},
            config,
            model_selector=selector,
        )

        # All providers lack vision support — filter removes them all, falls back to full list
        result = await router.route(
            [{"role": "user", "content": "describe the image"}],
            required_capabilities=["supports_vision"],
        )

        assert result.is_ok()
        text_client.complete.assert_called_once()


# ---------------------------------------------------------------------------
# ModelSelector.select() — strategy matching + capability filtering
# ---------------------------------------------------------------------------


class TestModelSelectorCapabilities:
    def test_filter_by_capabilities_returns_capable_models(self):
        capabilities = {
            "vision-model": ModelCapabilities(
                max_tokens=64000,
                supports_functions=True,
                supports_vision=True,
            ),
            "text-only": ModelCapabilities(
                max_tokens=16000,
                supports_functions=True,
                supports_vision=False,
            ),
            "basic": ModelCapabilities(
                max_tokens=4096,
                supports_functions=False,
                supports_vision=False,
            ),
        }
        selector = ModelSelector(
            default_model="text-only", model_capabilities=capabilities
        )

        capable = selector._filter_by_capabilities(["supports_vision"])

        assert "vision-model" in capable
        assert "text-only" not in capable
        assert "basic" not in capable

    def test_filter_by_capabilities_multiple_requirements(self):
        capabilities = {
            "full-featured": ModelCapabilities(
                max_tokens=128000,
                supports_functions=True,
                supports_vision=True,
            ),
            "vision-no-tools": ModelCapabilities(
                max_tokens=64000,
                supports_functions=False,
                supports_vision=True,
            ),
            "text-only": ModelCapabilities(
                max_tokens=16000,
                supports_functions=True,
                supports_vision=False,
            ),
        }
        selector = ModelSelector(
            default_model="text-only", model_capabilities=capabilities
        )

        capable = selector._filter_by_capabilities(["supports_functions", "supports_vision"])

        assert "full-featured" in capable
        assert "vision-no-tools" not in capable
        assert "text-only" not in capable

    def test_filter_by_capabilities_none_returns_all(self):
        selector = _make_vision_selector()

        all_models = selector._filter_by_capabilities(None)

        assert set(all_models) == {"vision-model", "text-only-model"}

    def test_select_respects_required_capabilities(self):
        capabilities = {
            "vision-model": ModelCapabilities(
                max_tokens=64000,
                supports_functions=True,
                supports_vision=True,
            ),
            "text-only": ModelCapabilities(
                max_tokens=16000,
                supports_functions=True,
                supports_vision=False,
            ),
        }
        selector = ModelSelector(
            default_model="text-only", model_capabilities=capabilities
        )

        model = selector.select("look at this image", required_capabilities=["supports_vision"])

        assert model == "vision-model"
