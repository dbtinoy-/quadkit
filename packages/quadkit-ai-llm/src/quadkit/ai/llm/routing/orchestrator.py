"""Intelligent LLM orchestration and routing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from quadkit.ai.llm.exceptions import LLMError, sanitize_llm_error
from quadkit.ai.llm.types import ChatMessage, Role
from quadkit.contracts.ai.models import ModelRequest, ModelResponse
from quadkit.contracts.ai.providers import ModelCapability, SelectionStrategy
from quadkit.logging import get_logger, safe_error_type
from quadkit.result import Err, Ok, Result

if TYPE_CHECKING:
    from quadkit.ai.llm.registry.core import ProviderRegistry

logger = get_logger(__name__)


class OrchestratorError(LLMError):
    """Base orchestration error."""

    _code: str = "QK_ERR_LLM_025"


class NoSuitableModelError(OrchestratorError):
    """No model found that meets the requirements."""

    _code: str = "QK_ERR_LLM_026"


@dataclass(frozen=True)
class _ModelSelection:
    """Internal result of model selection.

    Attributes:
        provider: Provider name key in the registry.
        model_id: Selected model identifier.
    """

    provider: str
    model_id: str


class LLMOrchestrator:
    """Intelligent routing and orchestration of multiple LLM providers.

    Selects the optimal provider/model for a given request based on:
    - Required capabilities
    - Token/cost constraints
    - Latency requirements
    - Provider availability

    The selection strategy is read from ``request.extra_params["strategy"]``
    (a :class:`~quadkit.contracts.ai.providers.SelectionStrategy` value or
    its string equivalent). Defaults to ``CAPABILITY_MATCH``.
    """

    def __init__(self, registry: ProviderRegistry) -> None:
        """Initialize orchestrator with a provider registry.

        Args:
            registry: The provider registry containing all models.
        """
        self.registry = registry
        self._round_robin_index: int = 0

    async def execute(
        self, request: ModelRequest
    ) -> Result[ModelResponse, OrchestratorError]:
        """Execute a request using the best available model.

        Args:
            request: The model request.

        Returns:
            ``Ok(ModelResponse)`` on success, ``Err(OrchestratorError)`` on failure.
        """
        selection = self._select_model(request)
        if not selection:
            error: OrchestratorError = NoSuitableModelError(
                "No model found matching requirements"
            )
            logger.error(
                "no_suitable_model",
                required_capabilities=sorted(
                    c.value for c in (request.required_capabilities or set())
                ),
            )
            return Err(error)

        try:
            self.registry.get_provider(selection.provider)
        except KeyError as exc:
            logger.warning(
                "provider_not_registered",
                error_type=safe_error_type(exc),
            )
            raise OrchestratorError("Provider is not registered") from None

        logger.info("executing_request")

        # Client must be supplied pre-configured via the DI container. Callers can
        # pass a ready-made client in ``request.extra_params["client"]`` for testing
        # or for use cases where instantiation is managed externally.
        client = request.extra_params.get("client")
        if client is None:
            error = OrchestratorError(
                "No pre-configured client found in request.extra_params['client']. "
                "Resolve the client through the DI container before calling execute()."
            )
            logger.error("no_client_in_request")
            return Err(error)

        messages = [ChatMessage(role=Role.USER, content=request.prompt)]
        try:
            result = await client.complete(
                messages,
                model=selection.model_id,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
            )
        except Exception as e:  # noqa: BLE001 — any provider failure is an Err result, never a raw raise
            error_type = safe_error_type(e)
            error = OrchestratorError(
                "Provider request failed",
                details={"error_type": error_type},
            )
            logger.error("provider_error", error_type=error_type)
            return Err(error)

        if result.is_ok():
            completion = result.unwrap()
        else:
            llm_error = result.unwrap_err()
            safe_error = sanitize_llm_error(llm_error)
            return Err(
                OrchestratorError(
                    safe_error.message,
                    details=safe_error.details,
                )
            )
        tokens_used = completion.usage.total_tokens if completion.usage else 0
        logger.info("request_completed", tokens_used=tokens_used)
        return Ok(
            ModelResponse(
                content=completion.content,
                tokens_used=tokens_used,
                stop_reason=completion.finish_reason,
            )
        )

    def _select_model(self, request: ModelRequest) -> _ModelSelection | None:
        """Select the best model for a request using the configured strategy.

        Strategy is read from ``request.extra_params["strategy"]`` and defaults
        to :attr:`~quadkit.contracts.ai.providers.SelectionStrategy.CAPABILITY_MATCH`.

        Priority:
        1. Explicit ``model_id`` — find provider that owns this model in its default set.
        2. ``ROUND_ROBIN`` — rotate through capability-filtered providers.
        3. ``COST_OPTIMAL`` / ``LATENCY_OPTIMAL`` / ``CAPABILITY_MATCH`` / ``PREFERRED``
           — return the first capability-filtered provider (cost/latency data is not
           yet available in :class:`~quadkit.ai.llm.registry.core.ProviderRegistry`).

        Args:
            request: The model request.

        Returns:
            A :class:`_ModelSelection` with provider name and model ID, or ``None``
            if no suitable provider is found.
        """
        # Resolve selection strategy
        raw_strategy = request.extra_params.get(
            "strategy", SelectionStrategy.CAPABILITY_MATCH
        )
        try:
            strategy = SelectionStrategy(raw_strategy)
        except ValueError:
            logger.warning("unknown_strategy", fallback="capability_match")
            strategy = SelectionStrategy.CAPABILITY_MATCH

        # Explicit model ID takes precedence: find which provider owns it
        if request.model_id:
            for name in self.registry.list_providers():
                info = self.registry.get_provider(name)
                if request.model_id in info.default_models:
                    return _ModelSelection(provider=name, model_id=request.model_id)
            logger.warning("model_not_found")
            return None

        # Derive capability requirements from the request
        caps: set[ModelCapability] = request.required_capabilities or set()
        needs_tools = ModelCapability.FUNCTION_CALLING in caps
        needs_vision = ModelCapability.VISION in caps
        needs_streaming = ModelCapability.STREAMING in caps

        candidates = self.registry.search_providers(
            supports_streaming=True if needs_streaming else None,
            supports_tools=True if needs_tools else None,
            supports_vision=True if needs_vision else None,
        )

        available = [p for p in candidates if p.default_models]
        if not available:
            return None

        # Apply selection strategy
        if strategy == SelectionStrategy.ROUND_ROBIN:
            chosen = available[self._round_robin_index % len(available)]
            self._round_robin_index = (self._round_robin_index + 1) % len(available)
        else:
            # COST_OPTIMAL, LATENCY_OPTIMAL, CAPABILITY_MATCH, PREFERRED:
            # Without real cost/latency data in the registry, fall back to first match.
            chosen = available[0]

        return _ModelSelection(provider=chosen.name, model_id=chosen.default_models[0])
