"""Multi-provider LLM router.

Cascades inference requests across configured providers in priority order.
Returns ``Result[InferenceLog, InferenceError]`` for explicit error handling.

The routing *strategy* is pluggable — see :mod:`.strategies` for the
``RoutingStrategyProtocol`` protocol and built-in implementations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.ai.llm.routing.strategies import (
    CostOptimizedStrategy,
    LatencyOptimizedStrategy,
    ParallelRaceStrategy,
    RoutingStrategyProtocol,
    SequentialCascadeStrategy,
)
from quadkit.ai.llm.routing.types import (
    InferenceError,
    InferenceLog,
    InferenceResult,
)
from quadkit.logging import get_logger, safe_error_type
from quadkit.result import Err, Ok, Result

if TYPE_CHECKING:
    from quadkit.ai.llm.routing.config import LLMConfig
    from quadkit.ai.llm.selection.core import ModelSelector
    from quadkit.contracts.ai import LLMClientProtocol
    from quadkit.contracts.ai.providers import ProviderRegistryProtocol
    from quadkit.contracts.ai.routing import (
        InferenceLoggerProtocol,
        QuotaBackendProtocol,
    )

logger = get_logger(__name__)

__all__ = ["LLMRouter"]


class LLMRouter:
    """Multi-provider LLM router with pluggable strategy.

    Delegates to a ``RoutingStrategyProtocol`` for provider selection.
    Returns ``Result[InferenceLog, InferenceError]``.

    Example:
        >>> config = LLMConfig.from_env()
        >>> router = LLMRouter(clients=clients, quota_backend=backend, ...)
        >>> result = await router.route(messages=[{"role": "user", "content": "Hi"}])
        >>> if result.is_ok():
        ...     print(result.unwrap().result.content)
    """

    def __init__(
        self,
        clients: dict[str, LLMClientProtocol],
        quota_backend: QuotaBackendProtocol,
        inference_logger: InferenceLoggerProtocol,
        config: LLMConfig,
        strategy: RoutingStrategyProtocol | None = None,
        model_selector: ModelSelector | None = None,
        provider_registry: ProviderRegistryProtocol | None = None,
    ) -> None:
        """Initialise the router.

        Args:
            clients: Mapping of provider name to its ``LLMClientProtocol``.
            quota_backend: Quota tracking backend.
            inference_logger: Inference log persistence backend.
            config: Full routing configuration.
            strategy: Routing strategy; defaults to
                :class:`SequentialCascadeStrategy`.
            model_selector: Optional model selector for capability-based
                filtering.  When set, ``required_capabilities`` in kwargs
                are used to exclude providers whose models lack the
                requested capabilities.
            provider_registry: Optional provider registry from
                ``the optional provider``.  When set, additional clients
                registered in the provider registry are merged into the
                routing pool.
        """
        self._clients = clients
        self._quota = quota_backend
        self._logger = inference_logger
        self._config = config
        self._strategy: RoutingStrategyProtocol = (
            strategy or self._strategy_from_config(config)
        )
        self._model_selector = model_selector
        self._provider_registry = provider_registry
        self._closed = False

        # Merge provider registry clients into routing pool
        if self._provider_registry:
            self._merge_registry_clients()

    @property
    def strategy(self) -> RoutingStrategyProtocol:
        """Return the active routing strategy."""
        return self._strategy

    @strategy.setter
    def strategy(self, value: RoutingStrategyProtocol) -> None:
        """Hot-swap the routing strategy at runtime."""
        self._strategy = value

    def _merge_registry_clients(self) -> None:
        """Merge clients from the provider registry into the routing pool.

        Only adds clients for providers not already in the pool, avoiding
        duplicates. This is called once at construction time.
        """
        if self._provider_registry is None:
            return
        try:
            for name in self._provider_registry.list_providers():
                if name not in self._clients:
                    # get_client is async but we can't await here; defer to route()
                    logger.debug("router_registry_has_additional_provider")
        except Exception as exc:  # noqa: BLE001 — registry merge is best-effort
            logger.warning(
                "router: failed to merge registry clients",
                error_type=safe_error_type(exc),
            )

    async def route(
        self,
        messages: list[Any],
        **kwargs: Any,
    ) -> Result[InferenceLog, InferenceError]:
        """Route a completion request across configured providers.

        Args:
            messages: OpenAI-compatible message list.
            **kwargs: Generation overrides forwarded to client (temperature,
                max_tokens, model, etc.).

        Returns:
            ``Ok(InferenceLog)`` on success, ``Err(InferenceError)`` when
            every provider (including paid fallback) is exhausted or fails.
        """
        # ``context`` is routing metadata, not a generation parameter. Keep it
        # out of provider client kwargs and retain it on both success and failure
        # records for application-level correlation (for example analysis_id).
        context = kwargs.pop("context", {})
        if not isinstance(context, dict):
            context = {}

        result, providers_tried, total_attempts = await self._strategy.execute(
            providers=self._filter_by_capabilities(
                self._config.providers,
                kwargs,
            ),
            clients=self._clients,
            quota=self._quota,
            config=self._config,
            messages=messages,
            kwargs=kwargs,
        )

        if result is not None:
            log = InferenceLog(
                result=result,
                providers_tried=providers_tried,
                total_attempts=total_attempts,
                context=context,
            )
            await self._logger.log(log)
            return Ok(log)

        terminal_error = InferenceError(
            message="All LLM providers exhausted or unavailable",
            providers_tried=providers_tried,
        )
        log = InferenceLog(
            error=terminal_error,
            providers_tried=providers_tried,
            total_attempts=total_attempts,
            context=context,
        )
        await self._logger.log(log)
        return Err(terminal_error)

    async def health_probe(self) -> Result[InferenceLog, InferenceError]:
        """Probe configured providers without performing normal inference.

        Returns:
            ``Ok(InferenceLog)`` for the first healthy enabled provider.
            The returned log is synthetic and is **not** persisted to the
            inference logger. ``Err(InferenceError)`` is returned when no
            healthy provider can be found.
        """
        providers_tried: list[str] = []
        total_attempts = 0

        for provider_config in self._config.providers:
            if not provider_config.enabled:
                continue

            client = self._clients.get(provider_config.key)
            if client is None:
                continue

            health_check = getattr(client, "health_check", None)
            if not callable(health_check):
                continue

            providers_tried.append(provider_config.name)
            total_attempts += 1
            try:
                health_result = await health_check(timeout=5.0)
            except Exception as exc:  # noqa: BLE001 — health probes must never raise — skip the provider
                logger.debug(
                    "llm_router_health_probe_failed",
                    error_type=safe_error_type(exc),
                )
                continue

            try:
                is_healthy = health_result.is_healthy()
            except (AttributeError, TypeError) as exc:
                logger.debug(
                    "llm_router_health_probe_failed",
                    error_type=safe_error_type(exc),
                )
                continue

            if is_healthy:
                try:
                    duration_ms = health_result.duration_ms
                except (AttributeError, TypeError) as exc:
                    logger.debug(
                        "llm_router_health_probe_failed",
                        error_type=safe_error_type(exc),
                    )
                    continue

                return Ok(
                    InferenceLog(
                        result=InferenceResult(
                            provider=provider_config.name,
                            model=provider_config.model,
                            content="health_probe",
                            attempt=total_attempts,
                            prompt_tokens=0,
                            completion_tokens=0,
                            latency_ms=duration_ms,
                        ),
                        providers_tried=providers_tried,
                        total_attempts=total_attempts,
                        context={"health_probe": True},
                    )
                )

            try:
                status = str(health_result.status)
                error = health_result.error
            except (AttributeError, TypeError) as exc:
                logger.debug(
                    "llm_router_health_probe_failed",
                    error_type=safe_error_type(exc),
                )
                continue

            logger.debug(
                "llm_router_health_probe_unhealthy",
                status=status,
                error_present=error is not None,
            )

        return Err(
            InferenceError(
                message="No healthy LLM providers available for health probe",
                providers_tried=providers_tried,
            )
        )

    async def close(self) -> None:
        """Close all registered LLM clients and release connections.

        Iterates over every client in the provider pool and calls ``close()``
        if the method exists. Safe to call multiple times.
        """
        if self._closed:
            return
        self._closed = True
        for client in self._clients.values():
            closer = getattr(client, "close", None)
            if closer is not None:
                try:
                    await closer()
                    logger.debug("llm_router_client_closed")
                except Exception as exc:
                    logger.warning(
                        "llm_router_client_close_failed",
                        error_type=safe_error_type(exc),
                    )

    def _filter_by_capabilities(
        self,
        providers: list[Any],
        kwargs: dict[str, Any],
    ) -> list[Any]:
        """Filter providers whose models lack required capabilities.

        When ``required_capabilities`` is present in *kwargs* and a
        ``ModelSelector`` is configured, only providers whose primary
        model satisfies **all** requested capabilities are retained.
        Providers whose model is unknown to the selector are kept
        (fail-open) so the strategy can still attempt them.

        Returns:
            Filtered provider list (original list when no filtering applies).
        """
        required: list[str] | None = kwargs.get("required_capabilities")
        if not required or self._model_selector is None:
            return providers

        capable_models = set(
            self._model_selector._filter_by_capabilities(required),
        )

        filtered = []
        for pcfg in providers:
            model = pcfg.model
            # Keep providers whose model is in the capable set or unknown
            # to the selector (fail-open avoids silently dropping custom models).
            if (
                model in capable_models
                or model not in self._model_selector.model_capabilities
            ):
                filtered.append(pcfg)
            else:
                logger.debug(
                    "router_provider_skipped_for_capabilities",
                    required_capability_count=len(required),
                )

        # If filtering removed everything, fall back to original list to
        # avoid a guaranteed "all providers exhausted" error.
        if not filtered:
            logger.warning(
                "router: no providers match required_capabilities %s; "
                "falling back to full provider list",
                required,
            )
            return providers

        return filtered

    @staticmethod
    def _strategy_from_config(config: LLMConfig) -> RoutingStrategyProtocol:
        """Build a :class:`RoutingStrategyProtocol` from the ``strategy`` config field.

        Falls back to :class:`SequentialCascadeStrategy` for unknown values.
        ``CostOptimizedStrategy`` requires a ``PricingManager``; when none
        is available it falls back to sequential with a warning.
        """
        name = getattr(config, "strategy", "sequential")
        if name == "parallel_race":
            return ParallelRaceStrategy()
        if name == "cost_optimized":
            try:
                from quadkit.ai.llm.pricing import PricingManager

                return CostOptimizedStrategy(PricingManager.from_defaults())
            except Exception:  # noqa: BLE001 — optional strategy init falls back to sequential cascade
                logger.warning(
                    "cost_optimized strategy requested but PricingManager "
                    "unavailable; falling back to sequential",
                )
                return SequentialCascadeStrategy()
        if name == "latency_optimized":
            return LatencyOptimizedStrategy()
        return SequentialCascadeStrategy()
