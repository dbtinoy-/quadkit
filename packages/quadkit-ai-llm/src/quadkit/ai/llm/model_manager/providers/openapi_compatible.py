"""OpenAPI-compatible model manager implementation.

Generic provider for OpenAI-compatible APIs like LM Studio, VLLM, Ollama, etc.
"""

from __future__ import annotations

import asyncio
from typing import Any

try:
    import aiohttp
except ImportError:
    aiohttp = None  # type: ignore[assignment]

from quadkit.ai.llm.model_manager.base import AbstractModelManager
from quadkit.ai.llm.model_manager.types import ModelLoadResult
from quadkit.logging import (
    get_logger,
)

logger = get_logger(__name__)


class OpenAPICompatibleModelManager(AbstractModelManager):
    """Generic model manager for OpenAI-compatible APIs.

    Supports LM Studio, VLLM, Ollama, and other OpenAI-compatible endpoints.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        provider_name: str = "openapi-compatible",
        api_version: str = "v1",
        supports_model_loading: bool = False,
        supports_model_switching: bool = False,
    ):
        """Initialize OpenAPI-compatible model manager.

        Args:
            base_url: Base URL of the API server
            provider_name: Name identifier for the provider
            api_version: API version (v1, v1beta, etc.)
            supports_model_loading: Whether the API supports explicit model loading
            supports_model_switching: Whether the API supports model switching
        """
        super().__init__(base_url, f"{provider_name}-model-manager")
        self.api_version = api_version
        self.supports_model_loading = supports_model_loading
        self.supports_model_switching = supports_model_switching
        self._loaded_models: dict[str, Any] = {}  # model_name -> handle/metadata

    async def list_models(self) -> list[dict[str, Any]]:
        """List available models via OpenAI-compatible API."""
        client = await self._get_client()
        resp = await client.get(f"/{self.api_version}/models")
        resp.raise_for_status()
        data = resp.json()
        if asyncio.iscoroutine(data):
            data = await data

        models = data["data"]
        return [
            {
                "name": model["id"],
                "details": model,
            }
            for model in models
        ]

    async def load_model(self, model_name: str, **kwargs: Any) -> ModelLoadResult:
        """Load a model via OpenAI-compatible API."""
        if model_name in self._loaded_models:
            logger.info("model_already_loaded")
            return ModelLoadResult(success=True, model_name=model_name)

        if not self.supports_model_loading:
            # For APIs that don't support explicit loading, just test connectivity
            try:
                await self._test_model_access(model_name)
                self._loaded_models[model_name] = None
                logger.info("model_prepared")
                return ModelLoadResult(success=True, model_name=model_name)
            except Exception as e:  # noqa: BLE001 — model access failures are ModelLoadResult, never raw raises
                error_type = type(e).__name__
                logger.warning(
                    "model_access_check_failed",
                    error_type=error_type,
                )
                return ModelLoadResult(
                    success=False,
                    model_name=model_name,
                    error=f"Failed to access model ({error_type})",
                    retryable=True,
                )

        # For APIs that support explicit loading (future implementation)
        # This would make specific API calls to load models
        logger.warning("explicit_model_loading_not_implemented")
        return ModelLoadResult(
            success=False,
            model_name=model_name,
            error="Explicit model loading is not supported",
        )

    async def unload_model(self, model_name: str) -> bool:
        """Unload a model."""
        if model_name not in self._loaded_models:
            logger.info("model_not_loaded")
            return True

        if not self.supports_model_loading:
            # For APIs that don't support explicit unloading, just remove from tracking
            del self._loaded_models[model_name]
            logger.info("model_marked_unloaded")
            return True

        # For APIs that support explicit unloading (future implementation)
        logger.warning("explicit_model_unloading_not_implemented")
        return False

    async def switch_model(self, model_name: str, **kwargs: Any) -> ModelLoadResult:
        """Switch to a different model."""
        if not self.supports_model_switching:
            # For APIs that don't support switching, unload all and load new one
            current_models = list(self._loaded_models.keys())
            for model in current_models:
                if model != model_name:
                    await self.unload_model(model)

            return await self.load_model(model_name, **kwargs)

        # For APIs that support explicit switching (future implementation)
        logger.warning("explicit_model_switching_not_implemented")
        return ModelLoadResult(
            success=False,
            model_name=model_name,
            error="Model switching is not supported",
        )

    async def get_loaded_models(self) -> list[str]:
        """Get currently loaded models."""
        return list(self._loaded_models.keys())

    async def _test_model_access(self, model_name: str) -> None:
        """Test if a model is accessible by making a minimal API call."""
        client = await self._get_client()

        # Make a minimal completion request to test model access
        test_payload = {
            "model": model_name,
            "messages": [{"role": "user", "content": "test"}],
            "max_tokens": 1,
            "temperature": 0,
        }

        resp = await client.post(
            f"/{self.api_version}/chat/completions",
            json=test_payload,
        )
        resp.raise_for_status()


class LMStudioModelManager(OpenAPICompatibleModelManager):
    """Model manager for LM Studio using OpenAPI-compatible base."""

    def __init__(self, base_url: str = "http://localhost:1234"):
        super().__init__(
            base_url=base_url,
            provider_name="lmstudio",
            api_version="v1",
            supports_model_loading=False,  # LM Studio loads on demand
            supports_model_switching=False,  # No explicit switching API
        )

    async def get_loaded_models(self) -> list[str]:
        """Get currently loaded models in LM Studio."""
        client = await self._get_client()
        response = await client.list_loaded_models()  # type: ignore[attr-defined]
        return [m.identifier for m in response]


class VLLMModelManager(OpenAPICompatibleModelManager):
    """Model manager for VLLM using OpenAPI-compatible base."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        super().__init__(
            base_url=base_url,
            provider_name="vllm",
            api_version="v1",
            supports_model_loading=False,  # VLLM manages loading internally
            supports_model_switching=False,  # No explicit switching API
        )
