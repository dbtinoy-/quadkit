"""Tests for the LLM orchestrator."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.ai.llm.exceptions import LLMError
from quadkit.ai.llm.registry.core import ProviderRegistry
from quadkit.ai.llm.routing.orchestrator import (
    LLMOrchestrator,
    NoSuitableModelError,
    OrchestratorError,
)
from quadkit.ai.llm.types import Completion, TokenUsage
from quadkit.contracts.ai.models import ModelRequest
from quadkit.contracts.ai.providers import ModelCapability
from quadkit.result import Err, Ok


class TestLLMOrchestrator:
    """Test suite for LLMOrchestrator."""

    @pytest.fixture
    def registry(self) -> ProviderRegistry:
        """Create a fresh registry."""
        return ProviderRegistry.with_defaults()

    @pytest.fixture
    def orchestrator(self, registry: ProviderRegistry) -> LLMOrchestrator:
        """Create an orchestrator with a registry."""
        return LLMOrchestrator(registry)

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create a mock LLM client."""
        client = MagicMock()
        response = Completion(
            content="Generated response",
            model="gpt-4",
            usage=TokenUsage(
                prompt_tokens=60,
                completion_tokens=40,
                total_tokens=100,
            ),
        )
        client.complete = AsyncMock(return_value=Ok(response))
        return client

    @pytest.mark.asyncio
    async def test_execute_with_explicit_model(
        self,
        orchestrator: LLMOrchestrator,
        mock_client: MagicMock,
    ) -> None:
        """Test execution with explicitly specified model."""
        request = ModelRequest(
            model_id="gpt-4-turbo",
            prompt="What is 2+2?",
            extra_params={"client": mock_client},
        )

        result = await orchestrator.execute(request)

        assert result.is_ok()
        response = result.unwrap()
        assert response.content == "Generated response"
        mock_client.complete.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_execute_with_capability_filter(
        self,
        orchestrator: LLMOrchestrator,
        mock_client: MagicMock,
    ) -> None:
        """Test execution with capability-based model selection."""
        request = ModelRequest(
            prompt="Generate image description",
            required_capabilities={ModelCapability.VISION},
            extra_params={"client": mock_client},
        )

        result = await orchestrator.execute(request)

        assert result.is_ok()
        response = result.unwrap()
        assert response.content == "Generated response"

    @pytest.mark.asyncio
    async def test_execute_no_suitable_model_hides_model_identifier(
        self,
        orchestrator: LLMOrchestrator,
        capsys,
    ) -> None:
        """Unmatched deployment identifiers stay out of errors and logs."""
        private_model_id = "private-model-deployment-123"
        request = ModelRequest(
            model_id=private_model_id,
            prompt="Some prompt",
        )

        result = await orchestrator.execute(request)

        assert result.is_err()
        error = result.unwrap_err()
        assert isinstance(error, NoSuitableModelError)
        assert private_model_id not in str(error)
        captured = capsys.readouterr()
        assert private_model_id not in captured.out + captured.err

    @pytest.mark.asyncio
    async def test_execute_provider_unavailable_hides_provider_identifier(
        self,
        orchestrator: LLMOrchestrator,
        registry: ProviderRegistry,
        mock_client: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
        capsys,
    ) -> None:
        """Provider identifiers and lookup error text are not exposed."""
        private_detail = "private-provider-name /srv/tenant-42/provider.json"
        request = ModelRequest(
            prompt="Test",
            required_capabilities={ModelCapability.VISION},
            extra_params={"client": mock_client},
        )

        monkeypatch.setattr(
            registry,
            "get_provider",
            MagicMock(side_effect=KeyError(private_detail)),
        )
        with pytest.raises(OrchestratorError) as exc_info:
            await orchestrator.execute(request)

        message = str(exc_info.value)
        assert private_detail not in message
        assert "private-provider-name" not in message
        assert "/srv/tenant-42/provider.json" not in message
        captured = capsys.readouterr()
        assert private_detail not in captured.out + captured.err
        assert "private-provider-name" not in captured.out + captured.err
        assert "/srv/tenant-42/provider.json" not in captured.out + captured.err

    @pytest.mark.asyncio
    async def test_execute_client_exception_text_is_not_exposed(
        self,
        orchestrator: LLMOrchestrator,
        capsys,
    ) -> None:
        """Raised provider exception text is not returned or logged."""
        secret = "ORCHESTRATOR_EXCEPTION_SECRET_SENTINEL"
        error_client = MagicMock()
        error_client.complete = AsyncMock(side_effect=RuntimeError(secret))
        request = ModelRequest(
            model_id="gpt-4",
            prompt="Test",
            extra_params={"client": error_client},
        )

        result = await orchestrator.execute(request)

        assert result.is_err()
        error = result.unwrap_err()
        assert secret not in str(error)
        assert secret not in repr(error.to_dict())
        captured = capsys.readouterr()
        assert secret not in captured.out + captured.err

    @pytest.mark.asyncio
    async def test_execute_client_result_error_is_sanitized(
        self,
        orchestrator: LLMOrchestrator,
    ) -> None:
        """Returned provider errors are not copied into orchestration errors."""
        secret = "ORCHESTRATOR_RESULT_SECRET_SENTINEL"
        error_client = MagicMock()
        error_client.complete = AsyncMock(return_value=Err(LLMError(secret)))
        request = ModelRequest(
            model_id="gpt-4",
            prompt="Test",
            extra_params={"client": error_client},
        )

        result = await orchestrator.execute(request)

        assert result.is_err()
        error = result.unwrap_err()
        assert secret not in str(error)
        assert secret not in repr(error.to_dict())

    @pytest.mark.asyncio
    async def test_select_model_explicit_id(
        self,
        orchestrator: LLMOrchestrator,
    ) -> None:
        """Test model selection with explicit model ID."""
        request = ModelRequest(
            model_id="gpt-3.5-turbo",
            prompt="Test",
        )

        model = orchestrator._select_model(request)

        assert model is not None
        assert model.model_id == "gpt-3.5-turbo"

    @pytest.mark.asyncio
    async def test_select_model_by_capability(
        self,
        orchestrator: LLMOrchestrator,
    ) -> None:
        """Test model selection by capability."""
        request = ModelRequest(
            prompt="Generate image description",
            required_capabilities={ModelCapability.VISION},
        )

        model = orchestrator._select_model(request)

        assert model is not None
        assert model.provider == "openai"

    @pytest.mark.asyncio
    async def test_select_model_multiple_capabilities(
        self,
        orchestrator: LLMOrchestrator,
    ) -> None:
        """Test selecting model that supports multiple capabilities."""
        request = ModelRequest(
            prompt="Complex task",
            required_capabilities={ModelCapability.VISION, ModelCapability.FUNCTION_CALLING},
        )

        model = orchestrator._select_model(request)

        assert model is not None
        assert model.provider == "openai"
