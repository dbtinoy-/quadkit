"""Ollama model manager implementation."""

from __future__ import annotations

import asyncio
from typing import Any

ollama: Any = None
try:
    import ollama as ollama_module

    ollama = ollama_module
except ImportError:
    ollama = None

from quadkit.ai.llm.model_manager.base import AbstractModelManager
from quadkit.ai.llm.model_manager.types import ModelLoadResult
from quadkit.logging import (
    get_logger,
)

logger = get_logger(__name__)


class OllamaModelManager(AbstractModelManager):
    """Model manager for Ollama."""

    def __init__(self, base_url: str = "http://localhost:11434"):
        super().__init__(base_url, "ollama-model-manager")
        self.client = ollama.Client(host=self.base_url) if ollama is not None else None

    async def list_models(self) -> list[dict[str, Any]]:
        """List available models in Ollama."""
        if self.client is not None:
            response = await asyncio.to_thread(self.client.list)
            return [{"name": m["name"], "details": m} for m in response["models"]]

        client = await self._get_client()
        response = await client.get("/api/tags")
        response.raise_for_status()
        data = response.json()
        if asyncio.iscoroutine(data):
            data = await data
        models = data.get("models", []) if isinstance(data, dict) else []
        return [{"name": m.get("name", ""), "details": m} for m in models]

    async def load_model(self, model_name: str, **kwargs: Any) -> ModelLoadResult:
        """Load a model in Ollama (pull if not available)."""
        try:
            # Check if model exists
            if self.client is not None:
                models = await asyncio.to_thread(self.client.list)
                model_names = [m["name"] for m in models["models"]]

                if model_name not in model_names:
                    logger.info("ollama_model_pull_started")
                    await asyncio.to_thread(self.client.pull, model_name)
                    logger.info("ollama_model_pull_succeeded")

                # Load model by making a simple generate request
                await asyncio.to_thread(
                    self.client.generate,
                    model=model_name,
                    prompt="test",
                    options={"num_predict": 1},
                )
            else:
                client = await self._get_client()
                pull_resp = await client.post("/api/pull", json={"name": model_name})
                pull_resp.raise_for_status()
                gen_resp = await client.post(
                    "/api/generate",
                    json={"model": model_name, "prompt": "test", "stream": False},
                )
                gen_resp.raise_for_status()
            logger.info("ollama_model_load_succeeded")
            return ModelLoadResult(success=True, model_name=model_name)

        except TimeoutError:
            return ModelLoadResult(
                success=False,
                model_name=model_name,
                error="Timed out loading model",
                retryable=True,
            )
        except (ConnectionError, OSError) as e:
            error_type = type(e).__name__
            return ModelLoadResult(
                success=False,
                model_name=model_name,
                error=f"Network error loading model ({error_type})",
                retryable=True,
            )
        except Exception as e:
            error_type = type(e).__name__
            logger.error(
                "ollama_model_load_failed",
                error_type=error_type,
            )
            return ModelLoadResult(
                success=False,
                model_name=model_name,
                error=f"Unexpected error loading model ({error_type})",
                retryable=False,
            )

    async def unload_model(self, model_name: str) -> bool:
        """Unload a model from Ollama memory."""
        # Ollama doesn't have explicit unload API
        # Models stay loaded until server restart or memory pressure
        # For our "1 model at a time" policy, we just log that it will be unloaded when another is loaded
        logger.info("ollama_models_unload_automatically")
        return True

    async def switch_model(self, model_name: str, **kwargs: Any) -> ModelLoadResult:
        """Switch to a different model (unload others first for 1-at-a-time policy)."""
        # Get currently loaded models
        loaded = await self.get_loaded_models()
        # Unload all except the target
        for m in loaded:
            if m != model_name:
                await self.unload_model(m)

        return await self.load_model(model_name, **kwargs)

    async def get_loaded_models(self) -> list[str]:
        """Get currently loaded models (Ollama tracks this via ps)."""
        if self.client is not None:
            response = await asyncio.to_thread(self.client.ps)
            # If the client returns a coroutine for ps(), await it
            if asyncio.iscoroutine(response):
                response = await response
            models = response["models"]
            return [m["name"] for m in models]

        client = await self._get_client()
        response = await client.get("/api/ps")
        response.raise_for_status()
        data = response.json()
        if asyncio.iscoroutine(data):
            data = await data
        models = data.get("models", []) if isinstance(data, dict) else []
        return [m.get("name", "") for m in models]
