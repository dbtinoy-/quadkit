"""Paid fallback routing strategy.

Encapsulates the paid-provider logic so that :class:`LLMRouter` no longer
embeds application-level "free vs. paid" business logic directly.  Users
opt-in by constructing a :class:`PaidFallbackStrategy` and passing it to
the router — or by continuing to pass ``paid_client`` to the router, which
builds this strategy automatically.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from quadkit.ai.llm.routing.strategies.base import _attempt_provider, _gen_defaults
from quadkit.ai.llm.types import AIError
from quadkit.logging import get_logger, safe_error_type

if TYPE_CHECKING:
    from quadkit.ai.llm.routing.config import (
        LLMConfig,
        ProviderConfig,
    )
    from quadkit.ai.llm.routing.types import (
        InferenceResult,
    )
    from quadkit.contracts.ai import LLMClientProtocol
    from quadkit.contracts.ai.routing import QuotaBackendProtocol


@dataclass
class PaidFallbackConfig:
    """Configuration for paid fallback routing."""

    provider: str
    models: list[str]

    @property
    def is_usable(self) -> bool:
        """Check if this config has a provider and at least one model."""
        return bool(self.provider and self.models)


logger = get_logger(__name__)


class PaidFallbackStrategy:
    """Routing strategy that attempts the paid fallback provider.

    Iterates over ``paid_config.models`` in order, returning on first
    success.  Intended as the final strategy in a chain after free
    providers are exhausted.

    Example:
        >>> strategy = PaidFallbackStrategy(paid_client, config.paid_fallback)
        >>> router = LLMRouter(..., paid_client=paid_client)
    """

    def __init__(
        self,
        client: LLMClientProtocol,
        paid_config: PaidFallbackConfig,
    ) -> None:
        """Initialise the paid fallback strategy.

        Args:
            client: LLM client for the paid provider.
            paid_config: Paid fallback configuration including provider name
                and ordered model list.
        """
        self._client = client
        self._paid_config = paid_config

    async def execute(
        self,
        *,
        providers: list[ProviderConfig],
        clients: dict[str, LLMClientProtocol],
        quota: QuotaBackendProtocol,
        config: LLMConfig,
        messages: list[Any],
        kwargs: dict[str, Any],
    ) -> tuple[InferenceResult | None, list[str], int]:
        """Attempt inference via the paid provider.

        The ``providers``, ``clients``, and ``quota`` arguments are part of
        the :class:`RoutingStrategy` protocol but are intentionally unused
        here — this strategy routes exclusively through its own pre-built
        ``client`` and ``paid_config``.

        Args:
            providers: Free-provider configs (unused).
            clients: Free-provider client map (unused).
            quota: Quota backend (unused).
            config: Full routing config for generation defaults.
            messages: OpenAI-compatible message list.
            kwargs: Generation overrides (temperature, max_tokens, model …).

        Returns:
            Tuple of ``(InferenceResult | None, providers_tried, total_attempts)``.
        """
        if not self._paid_config.is_usable:
            return None, [], 0

        temperature, max_tokens = _gen_defaults(config, kwargs)
        providers_tried: list[str] = []
        total_attempts = 0

        for paid_model in self._paid_config.models:
            provider_label = f"paid:{self._paid_config.provider}"
            providers_tried.append(provider_label)
            total_attempts += 1
            try:
                result = await _attempt_provider(
                    client=self._client,
                    provider_name=self._paid_config.provider,
                    model=paid_model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                result.is_paid = True
                logger.info("paid_fallback_succeeded")
                return result, providers_tried, total_attempts
            except AIError as exc:
                logger.error(
                    "paid_fallback_provider_failed",
                    error_type=safe_error_type(exc),
                )

        return None, providers_tried, total_attempts
