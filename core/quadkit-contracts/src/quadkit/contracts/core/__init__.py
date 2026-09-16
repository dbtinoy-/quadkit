from __future__ import annotations

from quadkit.contracts.core.clock import ClockProtocol, Duration
from quadkit.contracts.core.concurrency_enums import (
    ConcurrencyStrategy,
    ExecutionStrategy,
)
from quadkit.contracts.core.concurrency_protocols import (
    ChannelProtocol,
    DispatcherProtocol,
    ParallelProtocol,
    TaskManagerProtocol,
)
from quadkit.contracts.core.config import ConfigIssue, ConfigProtocol, Environment
from quadkit.contracts.core.constants import (
    ALL_ENTRY_POINT_GROUPS,
    EP_AI_SUBSYSTEMS,
    EP_PROVIDERS,
)
from quadkit.contracts.core.context import (
    ContextProtocol,
    RequestContextProtocol,
)
from quadkit.contracts.core.di import (
    ContainerProtocol,
    ContainerRegistrarProtocol,
    ContainerResolverProtocol,
)
from quadkit.contracts.core.disposable import AsyncDisposableProtocol
from quadkit.contracts.core.health import (
    AggregateHealthResult,
    HealthCheckableProtocol,
    HealthCheckAggregatorProtocol,
    HealthCheckCategory,
    HealthCheckProtocol,
    HealthCheckResult,
    HealthStatus,
)
from quadkit.contracts.core.hooks import HookPriority, HookRegistryProtocol
from quadkit.contracts.core.idempotency import IdempotencyStoreProtocol
from quadkit.contracts.core.identity import IdGeneratorProtocol, IdStrategy
from quadkit.contracts.core.invocation import (
    InvocationContextProtocol,
    InvocationHandlerProtocol,
    InvocationMiddlewareProtocol,
    InvocationPipelineProtocol,
)
from quadkit.contracts.core.lifecycle import (
    GracefulShutdownProtocol,
    OnApplicationBootstrapProtocol,
    OnApplicationShutdownProtocol,
    OnBeforeShutdownProtocol,
    OnConfigReloadProtocol,
    OnModuleInitProtocol,
)
from quadkit.contracts.core.lock import (
    AsyncLockProtocol,
    DistributedLockProtocol,
    LockInfo,
    LockManagerProtocol,
)
from quadkit.contracts.core.logging import LoggerProtocol
from quadkit.contracts.core.middleware import (
    ExceptionFilterChainProtocol,
    Middleware,
    MiddlewarePipelineProtocol,
    MiddlewareProtocol,
)
from quadkit.contracts.core.provider import (
    Lifecycle,
    ProviderPriority,
    ProviderProtocol,
)
from quadkit.contracts.core.registry import (
    BackendRegistryProtocol,
    RegistryProtocol,
    StrategyRegistryProtocol,
)
from quadkit.contracts.core.result import Err, Ok, Result
from quadkit.contracts.core.scopes import ServiceScope
from quadkit.contracts.core.serialization import (
    AsyncStringSerializerProtocol,
    JsonSerializerProtocol,
    SerializerProtocol,
)
from quadkit.contracts.core.stores import LockStoreProtocol as LockStoreProtocol
from quadkit.contracts.core.trace_context import (
    new_span_id,
    new_trace_id,
    span_id_var,
    trace_flags_var,
    trace_id_var,
)
from quadkit.contracts.core.types import (
    JSON,
    EntityId,
    Headers,
    Metadata,
    QueryParams,
    Timestamp,
    TokenPayload,
    Version,
)
from quadkit.contracts.core.validation import ValidationError
from quadkit.contracts.exceptions.container import OrphanedRegistration
from quadkit.contracts.infra.resilience import CircuitState

__all__ = [
    "JSON",
    "AggregateHealthResult",
    "AsyncDisposableProtocol",
    "AsyncLockProtocol",
    "AsyncStringSerializerProtocol",
    "BackendRegistryProtocol",
    "CircuitState",
    "ClockProtocol",
    "ConcurrencyStrategy",
    "ConfigIssue",
    "ConfigProtocol",
    "ContainerProtocol",
    "ContainerRegistrarProtocol",
    "ContainerResolverProtocol",
    "ContextProtocol",
    "DispatcherProtocol",
    "DistributedLockProtocol",
    "Duration",
    "EntityId",
    "Environment",
    "Err",
    "ExceptionFilterChainProtocol",
    "ExecutionStrategy",
    "GracefulShutdownProtocol",
    "Headers",
    "HealthCheckAggregatorProtocol",
    "HealthCheckCategory",
    "HealthCheckProtocol",
    "HealthCheckResult",
    "HealthCheckableProtocol",
    "HealthStatus",
    "HookPriority",
    "HookRegistryProtocol",
    "IdGeneratorProtocol",
    "IdStrategy",
    "IdempotencyStoreProtocol",
    "InvocationContextProtocol",
    "InvocationHandlerProtocol",
    "InvocationMiddlewareProtocol",
    "InvocationPipelineProtocol",
    "JsonSerializerProtocol",
    "Lifecycle",
    "LockInfo",
    "LockManagerProtocol",
    "LockStoreProtocol",
    "LoggerProtocol",
    "Metadata",
    "Middleware",
    "MiddlewarePipelineProtocol",
    "MiddlewareProtocol",
    "Ok",
    "OnApplicationBootstrapProtocol",
    "OnApplicationShutdownProtocol",
    "OnBeforeShutdownProtocol",
    "OnConfigReloadProtocol",
    "OnModuleInitProtocol",
    "OrphanedRegistration",
    "ParallelProtocol",
    "ProviderPriority",
    "ProviderProtocol",
    "QueryParams",
    "RegistryProtocol",
    "RequestContextProtocol",
    "Result",
    "SerializerProtocol",
    "ServiceScope",
    "StrategyRegistryProtocol",
    "TaskManagerProtocol",
    "Timestamp",
    "TokenPayload",
    "ValidationError",
    "Version",
    "new_span_id",
    "new_trace_id",
    "span_id_var",
    "trace_flags_var",
    "trace_id_var",
]
