"""Unit tests for embedding adapter health_check() return type alignment."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from quadkit.ai.llm.embedding.base import AbstractEmbeddingAdapter, EmbeddingModelInfo
from quadkit.ai.llm.embedding.config import EmbeddingConfig
from quadkit.contracts.core.health import HealthCheckResult, HealthStatus


class ConcreteEmbeddingAdapter(AbstractEmbeddingAdapter):
    """Minimal concrete adapter for testing the base health_check implementation."""

    async def embed(
        self,
        texts: str | list[str],
        *,
        model: str | None = None,
        batch_size: int = 100,
    ) -> list[list[float]]:
        return [[0.1, 0.2, 0.3]]

    def get_models(self) -> list[EmbeddingModelInfo]:
        return []


@pytest.fixture
def mock_adapter() -> ConcreteEmbeddingAdapter:
    """Provide a concrete adapter instance with a mock embed method."""
    config = EmbeddingConfig(model="test-model")
    adapter = ConcreteEmbeddingAdapter(config)
    adapter.embed = AsyncMock(return_value=[[0.1, 0.2, 0.3]])  # type: ignore[method-assign]
    return adapter


class TestEmbeddingHealthCheck:
    @pytest.mark.asyncio
    async def test_health_check_returns_health_check_result(
        self, mock_adapter: ConcreteEmbeddingAdapter
    ) -> None:
        result = await mock_adapter.health_check()
        assert isinstance(result, HealthCheckResult)
        assert result.status == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_health_check_unhealthy_on_exception(
        self, mock_adapter: ConcreteEmbeddingAdapter
    ) -> None:
        secret = "EMBEDDING_HEALTH_SECRET_SENTINEL"
        mock_adapter.embed = AsyncMock(side_effect=RuntimeError(secret))  # type: ignore[method-assign]
        result = await mock_adapter.health_check()
        assert isinstance(result, HealthCheckResult)
        assert result.status == HealthStatus.UNHEALTHY
        assert secret not in (result.message or "")
        assert secret not in (result.error or "")

    @pytest.mark.asyncio
    async def test_health_check_component_includes_model_name(
        self, mock_adapter: ConcreteEmbeddingAdapter
    ) -> None:
        result = await mock_adapter.health_check()
        assert "test-model" in result.component
