"""LLM multi-provider routing package.

Provides a cascade-style router that tries providers in priority order
and records every attempt via a pluggable quota backend and inference logger.

Quick start::

    from quadkit.ai.llm.routing import (
        LLMRouter,
        LLMConfig,
        ProviderConfig,
        InferenceResult,
        InferenceError,
        InferenceLog,
        InMemoryQuotaBackend,
        InMemoryInferenceLogger,
    )

    config = LLMConfig.from_env()
    router = LLMRouter(
        config=config,
        clients={},
        quota_backend=InMemoryQuotaBackend(),
        inference_logger=InMemoryInferenceLogger(),
    )
    result = await router.route(messages=[{"role": "user", "content": "Hello"}])
"""

from __future__ import annotations

from quadkit.ai.llm.routing.ab_split import ABSplitConfig, ABSplitStrategy
from quadkit.ai.llm.routing.backends.database import DatabaseQuotaBackend
from quadkit.ai.llm.routing.backends.memory import InMemoryQuotaBackend
from quadkit.ai.llm.routing.config import (
    GenerationDefaults,
    LLMConfig,
    LogConfig,
    ProviderConfig,
    QuotaConfig,
)
from quadkit.ai.llm.routing.loggers.database import DatabaseInferenceLogger
from quadkit.ai.llm.routing.loggers.memory import InMemoryInferenceLogger
from quadkit.ai.llm.routing.orchestrator import (
    LLMOrchestrator,
    NoSuitableModelError,
    OrchestratorError,
)
from quadkit.ai.llm.routing.router import LLMRouter
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
    ProviderUsage,
)

__all__ = [
    "ABSplitConfig",
    "ABSplitStrategy",
    "CostOptimizedStrategy",
    "DatabaseInferenceLogger",
    "DatabaseQuotaBackend",
    "GenerationDefaults",
    "InMemoryInferenceLogger",
    "InMemoryQuotaBackend",
    "InferenceError",
    "InferenceLog",
    "InferenceResult",
    "LLMConfig",
    "LLMOrchestrator",
    "LLMRouter",
    "LatencyOptimizedStrategy",
    "LogConfig",
    "NoSuitableModelError",
    "OrchestratorError",
    "ParallelRaceStrategy",
    "ProviderConfig",
    "ProviderUsage",
    "QuotaConfig",
    "RoutingStrategyProtocol",
    "SequentialCascadeStrategy",
]
