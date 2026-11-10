"""Base classes for model management."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from quadkit.ai.llm.http.client import ResilientHTTPClient
from quadkit.ai.llm.model_manager.types import ModelLoadResult
from quadkit.logging import (
    get_logger,
)

logger = get_logger(__name__)


class AbstractModelManager(ABC):
    """Abstract base class for LLM model managers."""

    def __init__(self, base_url: str, name: str = "model-manager"):
        self.base_url = base_url.rstrip("/")
        self.name = name
        self._client: ResilientHTTPClient | None = None

    async def _get_client(self) -> ResilientHTTPClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = ResilientHTTPClient(
                base_url=self.base_url,
                timeout=30.0,
                name=self.name,
            )
        return self._client

    @abstractmethod
    async def list_models(self) -> list[dict[str, Any]]:
        """List available models."""

    @abstractmethod
    async def load_model(self, model_name: str, **kwargs: Any) -> ModelLoadResult:
        """Load a model."""

    @abstractmethod
    async def unload_model(self, model_name: str) -> bool:
        """Unload a model."""

    @abstractmethod
    async def switch_model(self, model_name: str, **kwargs: Any) -> ModelLoadResult:
        """Switch to a different model."""

    @abstractmethod
    async def get_loaded_models(self) -> list[str]:
        """Get currently loaded models."""

    async def close(self) -> None:
        """Close the manager."""
        if self._client:
            await self._client.close()
            self._client = None
