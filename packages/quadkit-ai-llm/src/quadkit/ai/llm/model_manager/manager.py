"""Unified LLM model manager."""

from __future__ import annotations

import asyncio
from typing import Any

from quadkit.ai.llm.model_manager.base import AbstractModelManager
from quadkit.ai.llm.model_manager.providers import (
    LMStudioModelManager,
    OllamaModelManager,
    VLLMModelManager,
)
from quadkit.ai.llm.model_manager.types import ModelLoadResult
from quadkit.logging import (
    get_logger,
)

logger = get_logger(__name__)


class LLMModelManager:
    """Unified model manager that routes to specific provider managers.

    Instances are always empty — use :meth:`with_defaults` for the
    in-package built-in managers or :meth:`register_provider` for custom
    provider managers.
    """

    def __init__(self, active_provider: str | None = None):
        """Initialize an empty model manager."""
        self.managers: dict[str, AbstractModelManager] = {}
        self.active_provider = active_provider

    @classmethod
    def _default_entries(cls) -> tuple[tuple[str, AbstractModelManager], ...]:
        """The complete in-package built-in set, declared exactly once."""
        return (
            ("ollama", OllamaModelManager()),
            ("lm-studio", LMStudioModelManager()),
            ("vllm", VLLMModelManager()),
        )

    @classmethod
    def with_defaults(cls, active_provider: str | None = None) -> LLMModelManager:
        """Return an instance populated with the built-in provider managers."""
        manager = cls(active_provider=active_provider)
        for provider, provider_manager in cls._default_entries():
            manager.register_provider(provider, provider_manager)
        return manager

    def register_provider(self, provider: str, manager: AbstractModelManager) -> None:
        """Register a model manager for a provider."""
        self.managers[provider] = manager
        logger.debug("model_manager_provider_registered")

    def unregister_provider(self, provider: str) -> None:
        """Unregister a model manager."""
        if provider in self.managers:
            from quadkit.concurrency import TaskManager

            task_mgr = TaskManager()
            task_mgr.create_background_task(
                self.managers[provider].close(),
                name="model_manager_provider_shutdown",
            )
            del self.managers[provider]
            logger.info("model_manager_provider_unregistered")

    async def switch_provider(self, provider: str) -> bool:
        """Switch to a different provider and unload models from other providers."""
        if provider not in self.managers:
            logger.error("model_manager_provider_not_registered")
            return False

        # Unload models from other providers
        await self._unload_other_providers(provider)

        self.active_provider = provider
        logger.info("model_manager_provider_switched")
        return True

    async def _unload_other_providers(self, keep_provider: str) -> None:
        """Unload all models from providers other than the specified one."""
        for provider_name in self.managers:
            if provider_name != keep_provider:
                await self._unload_all_models(provider_name)

    async def _unload_all_models(self, provider: str) -> None:
        """Unload all models from a provider."""
        if provider not in self.managers:
            return

        # Try to get loaded models and unload them specifically
        loaded_models = await self.managers[provider].get_loaded_models()
        logger.info("model_manager_loaded_model_count", count=len(loaded_models))

        for model in loaded_models:
            await self.managers[provider].unload_model(model)

        # Check what models remain after unloading
        remaining_models = await self.managers[provider].get_loaded_models()
        logger.info(
            "model_manager_remaining_model_count",
            count=len(remaining_models),
        )

        # For providers that don't track loaded models well, we still attempt cleanup
        # This is especially important for local LLMs with limited GPU memory
        logger.info("model_manager_models_unloaded")

    async def list_models(self, provider: str | None = None) -> list[dict[str, Any]]:
        """List models for a provider."""
        target_provider = provider or self.active_provider
        if not target_provider or target_provider not in self.managers:
            return []

        return await self.managers[target_provider].list_models()

    @staticmethod
    def _safe_result(result: ModelLoadResult) -> ModelLoadResult:
        """Replace custom provider error text before it reaches callers."""
        if not result.success and result.error is not None:
            result.error = "Model operation failed"
        return result

    async def load_model(
        self,
        model_name: str,
        provider: str | None = None,
        **kwargs: Any,
    ) -> ModelLoadResult:
        """Load a model."""
        target_provider = provider or self.active_provider
        if not target_provider or target_provider not in self.managers:
            logger.error("model_manager_no_provider_for_load")
            return ModelLoadResult(
                success=False,
                model_name=model_name,
                error="No provider available for model loading",
                retryable=False,
            )

        # Explicitly unload models from other providers before loading new model
        logger.info("model_manager_unloading_previous_provider_models")
        await self._unload_other_providers(target_provider)

        # Add a small pause to ensure unloading takes effect
        await asyncio.sleep(0.5)

        # If switching providers, update active provider
        if provider and provider != self.active_provider:
            self.active_provider = provider

        logger.info("model_manager_load_started")
        result = self._safe_result(
            await self.managers[target_provider].load_model(model_name, **kwargs)
        )

        if result.success:
            logger.info("model_manager_load_succeeded")
        else:
            logger.error(
                "model_manager_load_failed", error_present=result.error is not None
            )

        return result

    async def unload_model(self, model_name: str, provider: str | None = None) -> bool:
        """Unload a model."""
        target_provider = provider or self.active_provider
        if not target_provider or target_provider not in self.managers:
            return False

        return await self.managers[target_provider].unload_model(model_name)

    async def switch_model(
        self,
        model_name: str,
        provider: str | None = None,
        **kwargs: Any,
    ) -> ModelLoadResult:
        """Switch to a different model."""
        target_provider = provider or self.active_provider
        if not target_provider or target_provider not in self.managers:
            return ModelLoadResult(
                success=False,
                model_name=model_name,
                error="Provider is not registered",
            )

        # Explicitly unload models from other providers before switching
        logger.info("model_manager_unloading_previous_models_before_switch")
        await self._unload_other_providers(target_provider)

        # Add a small pause to ensure unloading takes effect
        await asyncio.sleep(0.5)

        # If switching providers, update active provider
        if provider and provider != self.active_provider:
            self.active_provider = provider

        logger.info("model_manager_model_switch_started")
        result = await self.managers[target_provider].switch_model(model_name, **kwargs)
        return self._safe_result(result)

    async def get_loaded_models(self, provider: str | None = None) -> list[str]:
        """Get currently loaded models."""
        target_provider = provider or self.active_provider
        if not target_provider or target_provider not in self.managers:
            return []

        return await self.managers[target_provider].get_loaded_models()

    def get_current_provider(self) -> str | None:
        """Get the currently active provider."""
        return self.active_provider

    async def close(self) -> None:
        """Close all managers."""
        for manager in self.managers.values():
            await manager.close()
        self.managers.clear()
        logger.info("Closed all model managers")
