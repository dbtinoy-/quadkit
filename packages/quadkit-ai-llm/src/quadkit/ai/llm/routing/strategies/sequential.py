"""Sequential Cascade Routing Strategy."""

from __future__ import annotations

from typing import Any

from quadkit.ai.llm.routing.config import LLMConfig, ProviderConfig
from quadkit.ai.llm.routing.strategies.base import (
    _attempt_provider,
    _gen_defaults,
    _handle_free_failure,
)
from quadkit.ai.llm.routing.types import InferenceResult
from quadkit.ai.llm.types import AIError
from quadkit.contracts.ai import LLMClientProtocol
from quadkit.contracts.ai.routing import QuotaBackendProtocol
from quadkit.logging import (
    get_logger,
)

logger = get_logger(__name__)


class SequentialCascadeStrategy:
    """Try providers one at a time in configuration order.

    For each enabled, non-exhausted provider the strategy attempts the
    configured model once.
    """

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
        temperature, max_tokens = _gen_defaults(config, kwargs)
        providers_tried: list[str] = []
        total_attempts = 0

        for pcfg in providers:
            if not pcfg.enabled:
                continue
            client = clients.get(pcfg.key)
            if client is None:
                continue

            providers_tried.append(pcfg.name)

            if await quota.is_exhausted(pcfg.key):
                logger.debug("sequential_provider_skipped_exhausted")
                continue

            model = pcfg.model
            total_attempts += 1
            try:
                result = await _attempt_provider(
                    client=client,
                    provider_name=pcfg.name,
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                await quota.increment(pcfg.key)
                logger.info("sequential_provider_succeeded")
                return result, providers_tried, total_attempts
            except AIError as exc:
                await _handle_free_failure(
                    exc=exc,
                    provider_key=pcfg.key,
                    model=model,
                    quota=quota,
                    cooldown_seconds=config.quota.cooldown_seconds,
                )

        return None, providers_tried, total_attempts
