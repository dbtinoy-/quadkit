"""LLM module for dependency injection."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.contracts.ai import LLMClientProtocol
from quadkit.di.module import DynamicModule, Module, module

if TYPE_CHECKING:
    from quadkit.ai.llm.config import ClientConfig
    from quadkit.ai.llm.routing.config import LLMConfig


@module(is_global=True)
class LLMModule(Module):
    """LLM client and model-management integration.

    Declared global so its exports are visible to every module in the graph
    without explicit import — the LLM client is cross-cutting infrastructure
    consumed by agents, RAG, verification, and embedding pipelines.

    Call :meth:`configure` to register an :class:`~quadkit.contracts.ai.LLMClientProtocol`
    implementation and optional model manager for injection.

    Usage::

        from quadkit.ai.llm.config import ClientConfig

        @module(
            imports=[
                LLMModule.configure(
                    ClientConfig(provider="openai", model="gpt-4o")
                )
            ]
        )
        class AppModule(Module):
            pass

    Multi-provider routing::

        from quadkit.ai.llm import LLMModule

        @module(
            imports=[LLMModule.configure(routing=LLMConfig())]
        )
        class AppModule(Module):
            pass
    """

    @classmethod
    def configure(
        cls,
        config: ClientConfig | Any | None = None,
        *,
        routing: LLMConfig | Any | None = None,
        enable_model_manager: bool = False,
        enable_streaming: bool = True,
        audit_calls: bool = False,
    ) -> DynamicModule:
        """Create an LLMModule with a single configured provider.

        Args:
            config: :class:`~quadkit.ai.llm.config.ClientConfig` or ``None``
                to read configuration from environment variables.
            routing: Optional :class:`~quadkit.ai.llm.routing.config.LLMConfig`
                enabling the multi-provider routing layer instead of the
                single-provider client.
            enable_model_manager: Register :class:`~quadkit.ai.llm.model_manager.LLMModelManager`
                for local model lifecycle control.
            enable_streaming: Enable streaming response support. Defaults to
                ``True``; set to ``False`` to restrict to non-streaming clients only.
            audit_calls: Emit an ``AuditEntry`` per LLM completion via
                :class:`~quadkit.ai.llm.audit_bridge.LLMAuditBridge`. Requires
                ``AuditLoggerProtocol`` in the container. Default ``False``.

        Returns:
            A :class:`~quadkit.di.module.DynamicModule` descriptor.
        """
        if routing is not None:
            from quadkit.ai.llm.di.routing_provider import LLMRoutingProvider

            return DynamicModule(
                module=cls,
                providers=[LLMRoutingProvider(config=routing)],
                exports=[LLMClientProtocol],
            )

        from quadkit.ai.llm.di.provider import LLMProvider

        return DynamicModule(
            module=cls,
            providers=[
                LLMProvider(
                    config=config,
                    enable_model_manager=enable_model_manager,
                    enable_streaming=enable_streaming,
                    audit_calls=audit_calls,
                )
            ],
            exports=[LLMClientProtocol],
        )

    @classmethod
    def stub(cls, config: ClientConfig | Any | None = None) -> DynamicModule:
        """Create an LLMModule suitable for unit and integration testing.

        Uses a no-op or stub LLM client with minimal external dependencies.
        Streaming is disabled by default to simplify test assertions.

        Args:
            config: Optional :class:`~quadkit.ai.llm.config.ClientConfig` override.
                Uses safe test defaults when ``None``.

        Returns:
            A :class:`~quadkit.di.module.DynamicModule` descriptor.
        """
        from quadkit.ai.llm.di.provider import LLMProvider

        return DynamicModule(
            module=cls,
            providers=[
                LLMProvider(
                    config=config,
                    enable_model_manager=False,
                    enable_streaming=False,
                    stub_mode=True,
                )
            ],
            exports=[LLMClientProtocol],
        )


__all__ = ["LLMModule"]
