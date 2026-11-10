"""Parallel Race Routing Strategy."""

from __future__ import annotations

import asyncio
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


class ParallelRaceStrategy:
    """Fire requests to all eligible providers simultaneously.

    Returns the first successful result.  Remaining in-flight tasks are
    cancelled to conserve resources and avoid unnecessary billing.
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

        # Build list of eligible (entry config, client) pairs.
        candidates: list[tuple[ProviderConfig, LLMClientProtocol]] = []
        for pcfg in providers:
            if not pcfg.enabled:
                continue
            client = clients.get(pcfg.key)
            if client is None:
                continue
            providers_tried.append(pcfg.name)
            if await quota.is_exhausted(pcfg.key):
                continue
            candidates.append((pcfg, client))

        if not candidates:
            return None, providers_tried, 0

        # Fire all candidates concurrently.
        tasks: dict[asyncio.Task[InferenceResult], ProviderConfig] = {}
        for pcfg, client in candidates:
            task = asyncio.create_task(
                _attempt_provider(
                    client=client,
                    provider_name=pcfg.name,
                    model=pcfg.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                ),
            )
            tasks[task] = pcfg

        total_attempts = len(tasks)
        winner: InferenceResult | None = None
        pending = set(tasks.keys())

        try:
            while pending:
                done, pending = await asyncio.wait(
                    pending,
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for task in done:
                    pcfg = tasks[task]
                    if task.exception() is not None:
                        exc = task.exception()
                        if isinstance(exc, AIError):
                            await _handle_free_failure(
                                exc=exc,
                                provider_key=pcfg.key,
                                model=pcfg.model,
                                quota=quota,
                                cooldown_seconds=config.quota.cooldown_seconds,
                            )
                        continue
                    # First success wins.
                    winner = task.result()
                    await quota.increment(pcfg.key)
                    logger.info("parallel_race_winner_selected")
                    # Cancel remaining tasks.
                    for p in pending:
                        p.cancel()
                    break
        finally:
            # Ensure no dangling tasks.
            for t in tasks:
                if not t.done():
                    t.cancel()

        return winner, providers_tried, total_attempts
