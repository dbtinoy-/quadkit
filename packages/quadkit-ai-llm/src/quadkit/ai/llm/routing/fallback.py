"""Fallback chain for retrying with alternate models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from quadkit.ai.llm.exceptions import sanitize_llm_error
from quadkit.contracts.ai.models import ModelRequest, ModelResponse
from quadkit.logging import (
    get_logger,
)
from quadkit.result import Err, Ok, Result

if TYPE_CHECKING:
    from quadkit.ai.llm.health.circuit_breaker import (
        ProviderCircuitBreaker as HealthMonitor,
    )
    from quadkit.ai.llm.registry.core import ProviderRegistry
    from quadkit.ai.llm.selection.core import ModelSelector

logger = get_logger(__name__)


@dataclass
class FallbackAttempt:
    """Result of one attempt in a fallback chain.

    Attributes:
        model_id: Model that was tried
        provider: Provider name
        success: Whether the attempt succeeded
        error: Error message if failed
        fallback_reason: Why we fell back to next model
    """

    model_id: str
    provider: str
    success: bool
    error: str | None = None
    fallback_reason: str | None = None


class FallbackChain:
    """Executes request with fallback to alternate models.

    Tries primary model, then falls back to alternates if it fails.
    """

    def __init__(
        self,
        registry: ProviderRegistry,
        max_retries: int = 3,
        selector: ModelSelector | None = None,
        health_monitor: HealthMonitor | None = None,
    ) -> None:
        """Initialize fallback chain.

        Args:
            registry: Provider registry
            max_retries: Maximum number of attempts
            selector: Optional model selector for intelligent routing
            health_monitor: Optional health monitor for health-aware routing
        """
        self.registry = registry
        self.max_retries = max_retries
        self.selector = selector
        self.health_monitor = health_monitor
        self.attempts: list[FallbackAttempt] = []

    async def execute(
        self,
        messages: list[dict[str, Any]] | ModelRequest,
        model: str | None = None,
        max_attempts: int | None = None,
        model_ids: list[str] | None = None,
    ) -> Result[ModelResponse, Exception]:
        """Execute with fallback chain.

        Args:
            messages: List of message dicts or a ModelRequest
            model: Optional specific model ID to try first
            max_attempts: Override for max_retries
            model_ids: Explicit list of model IDs to try in order

        Returns:
            Result with response or final error
        """
        self.attempts = []

        effective_max = max_attempts or self.max_retries

        # Normalise input to ModelRequest
        if isinstance(messages, list):
            prompt = " ".join(
                m.get("content", "") for m in messages if isinstance(m, dict)
            )
            request = ModelRequest(prompt=prompt, model_id=model)
        else:
            request = messages

        if not model_ids:
            if model:
                model_ids = [model]
            if not model_ids:
                # Use all registered models
                available = self.registry.list_models()
                model_ids = [m.model_id for m in available]

        if not model_ids:
            error = RuntimeError("No models available for fallback chain")
            return Err(error)

        # Limit retries
        model_ids = model_ids[:effective_max]

        last_error = None
        for i, model_id in enumerate(model_ids):
            logger.info(
                "fallback_attempt",
                attempt=i + 1,
                max_retries=self.max_retries,
            )

            # Get model and client
            model_info = self.registry.get_model_info(model_id)
            if not model_info:
                error_msg = "Requested model is not registered"
                self.attempts.append(
                    FallbackAttempt(
                        model_id=model_id,
                        provider="unknown",
                        success=False,
                        error=error_msg,
                        fallback_reason="Model not found",
                    )
                )
                continue

            client = await self.registry.get_client(model_info.provider)
            if not client:
                error_msg = "Provider is unavailable"
                self.attempts.append(
                    FallbackAttempt(
                        model_id=model_id,
                        provider=model_info.provider,
                        success=False,
                        error=error_msg,
                        fallback_reason="Provider unavailable",
                    )
                )
                continue

            # Try to execute
            try:
                complete_messages = [{"role": "user", "content": request.prompt}]
                response = await client.complete(
                    complete_messages,  # type: ignore[arg-type]
                    model=model_id,
                    temperature=request.temperature
                    if isinstance(request, ModelRequest)
                    else None,
                    max_tokens=request.max_tokens
                    if isinstance(request, ModelRequest)
                    else None,
                )
                if isinstance(response, Result):
                    if response.is_err():
                        raise sanitize_llm_error(response.unwrap_err()) from None
                    response = response.unwrap()

                logger.info("fallback_success", attempt=i + 1)
                self.attempts.append(
                    FallbackAttempt(
                        model_id=model_id,
                        provider=model_info.provider,
                        success=True,
                    )
                )
                completion = (
                    response
                    if isinstance(response, str)
                    else (response.content if hasattr(response, "content") else "")
                )
                return Ok(ModelResponse(content=str(completion), tokens_used=0))
            except Exception as e:  # noqa: BLE001 — any provider failure is recorded and the fallback cascade continues
                safe_error = sanitize_llm_error(e)
                error_type = type(e).__name__
                last_error = safe_error
                fallback_reason = "Request failed"
                self.attempts.append(
                    FallbackAttempt(
                        model_id=model_id,
                        provider=model_info.provider,
                        success=False,
                        error=safe_error.message,
                        fallback_reason=fallback_reason,
                    )
                )

                if i < len(model_ids) - 1:
                    logger.warning(
                        "fallback_attempt_failed",
                        attempt=i + 1,
                        error_type=error_type,
                    )

        # All attempts exhausted
        final_error = last_error or RuntimeError("All fallback attempts failed")
        logger.error(
            "fallback_chain_exhausted",
            total_attempts=len(model_ids),
            last_error_type=type(final_error).__name__,
        )
        return Err(final_error)

    def get_attempt_details(self) -> list[FallbackAttempt]:
        """Get details of all attempts made.

        Returns:
            List of FallbackAttempt records
        """
        return self.attempts

    def get_success_model(self) -> str | None:
        """Get the model that succeeded.

        Returns:
            Model ID that succeeded, or None if all failed
        """
        for attempt in self.attempts:
            if attempt.success:
                return attempt.model_id
        return None
