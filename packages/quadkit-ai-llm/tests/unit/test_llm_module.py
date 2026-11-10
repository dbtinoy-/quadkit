"""Tests for LLM module."""

from __future__ import annotations

from quadkit.ai.llm import LLMModule
from quadkit.ai.llm.routing import LLMConfig
from quadkit.contracts.ai.llm import LLMClientProtocol
from quadkit.di.module import DynamicModule


class TestLLMModule:
    """Test suite for LLMModule."""

    def test_module_decorator_exists(self) -> None:
        """Verify @module decorator is applied to LLMModule."""
        assert hasattr(LLMModule, "__quadkit_module__")

    def test_configure_returns_dynamic_module(self) -> None:
        """Verify configure() returns DynamicModule instance."""
        result = LLMModule.configure(None)
        assert isinstance(result, DynamicModule)
        assert result.module is LLMModule

    def test_configure_exports_llm_client_protocol(self) -> None:
        """Verify configure() exports LLMClientProtocol."""
        result = LLMModule.configure(None)
        assert LLMClientProtocol in result.exports

    def test_configure_with_dict_config(self) -> None:
        """Verify configure() accepts dict configuration."""
        config = {"provider": "openai"}
        result = LLMModule.configure(config)
        assert isinstance(result, DynamicModule)
        assert result.module is LLMModule

    def test_configure_with_routing_uses_routing_provider(self) -> None:
        """Routing mode is selected through configure(routing=...)."""
        result = LLMModule.configure(routing=LLMConfig())

        assert isinstance(result, DynamicModule)
        assert type(result.providers[0]).__name__ == "LLMRoutingProvider"

    def test_legacy_routing_factories_are_removed(self) -> None:
        """Only configure()/stub() remain public for routing setup."""
        assert not hasattr(LLMModule, "for_routing")
        assert not hasattr(LLMModule, "routed")
