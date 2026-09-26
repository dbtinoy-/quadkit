"""Quadkit Unified Types.

This package provides a centralized location for all framework-wide
type definitions, protocols, and data classes.
"""

from __future__ import annotations

import pkgutil
from typing import TYPE_CHECKING, Any

__path__ = pkgutil.extend_path(__path__, __name__)

# -- Version ---------------------------------------------------------------

import importlib.metadata

from quadkit.contracts.core.constants import __version__ as __version__

# ---------------------------------------------------------------------------
# Lazy Imports (deferred until first attribute access)
# ---------------------------------------------------------------------------
if TYPE_CHECKING:
    from quadkit.contracts import (
        admin,
        ai,
        auth,
        core,
        data,
        domain,
        events,
        exceptions,
        feature_flags,
        graphql,
        infra,
        mapping,
        mcp,
        monitor,
        observability,
        search,
        security,
        tenancy,
        web,
        workflow,
    )
    from quadkit.contracts.ai import (
        AgentError,
        AgentExecutorProtocol,
        AgentProtocol,
        AgentResponse,
        AIProviderProtocol,
        ChatMessage,
        ContextPrunerProtocol,
        DocumentVectorStoreProtocol,
        EmbeddingClientProtocol,
        EpisodicMemoryProtocol,
        LLMClientProtocol,
        MemoryConsolidatorProtocol,
        MemoryProtocol,
        MemoryStoreProtocol,
        PromptAssemblerProtocol,
        PromptCompressorProtocol,
        SemanticCacheProtocol,
        SemanticMemoryProtocol,
        StrategyError,
        StrategyProtocol,
        TokenBudget,
        TokenCounterProtocol,
        ToolError,
        ToolProtocol,
        ToolRegistryProtocol,
        WorkingMemoryProtocol,
    )
    from quadkit.contracts.ai.workflow import AIWorkflowNodeProtocol
    from quadkit.contracts.audit import AuditEntry
    from quadkit.contracts.auth import (
        AuthenticatedUserProtocol,
        AuthorizerProtocol,
        AuthProviderProtocol,
        PasswordHasherProtocol,
        TokenManagerProtocol,
        UserProtocol,
    )
    from quadkit.contracts.cli import (
        CliContributorProtocol,
        GeneratorDefinition,
        GeneratorOption,
    )
    from quadkit.contracts.core import (
        JSON,
        AggregateHealthResult,
        AsyncStringSerializerProtocol,
        ClockProtocol,
        ConfigProtocol,
        ContainerProtocol,
        ContainerRegistrarProtocol,
        ContainerResolverProtocol,
        Duration,
        GracefulShutdownProtocol,
        HealthCheckAggregatorProtocol,
        HealthCheckProtocol,
        HealthCheckResult,
        HealthStatus,
        IdGeneratorProtocol,
        IdStrategy,
        Lifecycle,
        LockStoreProtocol,
        Metadata,
        OnApplicationBootstrapProtocol,
        OnApplicationShutdownProtocol,
        OnBeforeShutdownProtocol,
        OnModuleInitProtocol,
        ProviderPriority,
        ProviderProtocol,
        Result,
        SerializerProtocol,
        ServiceScope,
        TokenPayload,
    )
    from quadkit.contracts.core.idempotency import (
        IdempotencyMiddlewareProtocol,
        IdempotencyStoreProtocol,
    )
    from quadkit.contracts.core.lock import (
        AsyncLockProtocol,
        DistributedLockProtocol,
        LockInfo,
        LockManagerProtocol,
    )
    from quadkit.contracts.core.validation import ValidationError
    from quadkit.contracts.data import (
        ConnectionPoolProtocol,
        ConnectionProtocol,
        DatabaseProviderProtocol,
        DeleteResult,
        InsertResult,
        MigrationManagerProtocol,
        MigrationRecord,
        QueryLogEntry,
        QueryLoggerProtocol,
        QueryResult,
        ReadOnlyRepositoryProtocol,
        RepositoryProtocol,
        UnitOfWorkProtocol,
        UpdateResult,
    )
    from quadkit.contracts.data.sql.migrations import MigrationRunnerProtocol
    from quadkit.contracts.data.vector.protocols import VectorStoreProtocol
    from quadkit.contracts.domain.aggregates import AggregateRootProtocol
    from quadkit.contracts.domain.events import DomainEvent
    from quadkit.contracts.domain.pagination import (
        CursorPage,
        CursorPageProtocol,
        OffsetPageProtocol,
    )
    from quadkit.contracts.domain.specification import SpecificationProtocol
    from quadkit.contracts.events import (
        CommandBusProtocol,
        DomainEventPublisherProtocol,
        EventBusProtocol,
        EventHandlerProtocol,
        EventStoreProtocol,
        QueryBusProtocol,
        WebhookSignatureVerifierProtocol,
    )
    from quadkit.contracts.exceptions.components import (
        SecretNotFoundError,
    )
    from quadkit.contracts.exceptions.events import (
        DuplicateHandlerError,
        HandlerNotFoundError,
    )
    from quadkit.contracts.exceptions.security import (
        SecretAccessError,
    )
    from quadkit.contracts.feature_flags import (
        FlagEvaluation,
        FlagType,
        FlagValue,
    )
    from quadkit.contracts.infra.cache import (
        CacheAdminProtocol,
        CacheBackendProtocol,
        CacheProviderProtocol,
    )
    from quadkit.contracts.infra.redis import RedisClientProtocol
    from quadkit.contracts.infra.resilience import (
        CircuitBreakerConfig,
        RetryConfig,
    )
    from quadkit.contracts.infra.resources import (
        PoolManagerProtocol,
        PoolProtocol,
        PoolStatsProtocol,
    )
    from quadkit.contracts.infra.state import StateStoreProtocol
    from quadkit.contracts.infra.storage import BlobStoreProtocol
    from quadkit.contracts.infra.tasks import (
        JobProtocol,
        JobStatus,
        TaskExecutorProtocol,
        TaskProviderProtocol,
        TaskQueueProtocol,
    )
    from quadkit.contracts.mapping import ObjectMapperProtocol
    from quadkit.contracts.mcp import (
        MCPError,
        MCPInitializationError,
        MCPMethodNotFoundError,
        MCPPromptError,
        MCPProtocolError,
        MCPResourceError,
        MCPServerProtocol,
        MCPToolCallError,
        MCPToolProviderProtocol,
        MCPTransportProtocol,
    )
    from quadkit.contracts.observability.metrics import HealthCheckRegistryProtocol
    from quadkit.contracts.search import SearchEngineProtocol
    from quadkit.contracts.security import (
        AsyncSecretStoreProtocol,
        HasherProtocol,
        KeyDerivationProtocol,
    )
    from quadkit.contracts.security.secrets import SecretStoreProtocol
    from quadkit.contracts.tenancy import (
        TenantConfigError,
        TenantConfigProviderProtocol,
        TenantError,
        TenantInactiveError,
        TenantInfo,
        TenantIsolationStrategyProtocol,
        TenantNotFoundError,
        TenantProviderProtocol,
        TenantProvisioningError,
        TenantResolutionContext,
        TenantResolutionError,
        TenantResolverProtocol,
        TenantSlugConflictError,
        TenantStatus,
        TenantSuspendedError,
    )
    from quadkit.contracts.web import (
        CORSPolicyProtocol,
        ErrorDetail,
        ErrorResponseDTO,
        HttpRequestLoggerProtocol,
        PaginatedResponseDTO,
    )
    from quadkit.contracts.workflow import (
        SagaManagerProtocol,
        SagaProtocol,
    )

_SUBMODULE_NAMES: frozenset[str] = frozenset(
    {
        "admin",
        "ai",
        "auth",
        "cli",
        "codegen",
        "core",
        "data",
        "domain",
        "events",
        "exceptions",
        "feature_flags",
        "graphql",
        "infra",
        "lib",
        "lifecycle",
        "mailer",
        "mapping",
        "mcp",
        "monitor",
        "notification",
        "observability",
        "search",
        "security",
        "tenancy",
        "web",
        "workflow",
    }
)

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    # lifecycle
    "AuditableProtocol": ("quadkit.contracts.lifecycle", "AuditableProtocol"),
    "CacheAwareProtocol": ("quadkit.contracts.lifecycle", "CacheAwareProtocol"),
    "ExportableProtocol": ("quadkit.contracts.lifecycle", "ExportableProtocol"),
    "TransactionalProtocol": ("quadkit.contracts.lifecycle", "TransactionalProtocol"),
    "ValidatableProtocol": ("quadkit.contracts.lifecycle", "ValidatableProtocol"),
    # cli
    "CliContributorProtocol": ("quadkit.contracts.cli", "CliContributorProtocol"),
    "GeneratorDefinition": ("quadkit.contracts.cli", "GeneratorDefinition"),
    "GeneratorOption": ("quadkit.contracts.cli", "GeneratorOption"),
    # agents (merged into ai/)
    "AgentError": ("quadkit.contracts.ai", "AgentError"),
    "AgentExecutorProtocol": ("quadkit.contracts.ai", "AgentExecutorProtocol"),
    "AgentProtocol": ("quadkit.contracts.ai", "AgentProtocol"),
    "AgentResponse": ("quadkit.contracts.ai", "AgentResponse"),
    "StrategyError": ("quadkit.contracts.ai", "StrategyError"),
    "StrategyProtocol": ("quadkit.contracts.ai", "StrategyProtocol"),
    "ToolError": ("quadkit.contracts.ai", "ToolError"),
    "ToolProtocol": ("quadkit.contracts.ai", "ToolProtocol"),
    "ToolRegistryProtocol": ("quadkit.contracts.ai", "ToolRegistryProtocol"),
    # ai
    "AIProviderProtocol": ("quadkit.contracts.ai", "AIProviderProtocol"),
    "ChatMessage": ("quadkit.contracts.ai.llm", "ChatMessage"),
    "ContextPrunerProtocol": ("quadkit.contracts.ai.session", "ContextPrunerProtocol"),
    "EmbeddingClientProtocol": ("quadkit.contracts.ai", "EmbeddingClientProtocol"),
    "EpisodicMemoryProtocol": ("quadkit.contracts.ai", "EpisodicMemoryProtocol"),
    "LLMClientProtocol": ("quadkit.contracts.ai", "LLMClientProtocol"),
    "MemoryConsolidatorProtocol": (
        "quadkit.contracts.ai",
        "MemoryConsolidatorProtocol",
    ),
    "MemoryProtocol": ("quadkit.contracts.ai", "MemoryProtocol"),
    "MemoryStoreProtocol": ("quadkit.contracts.ai", "MemoryStoreProtocol"),
    "PromptAssemblerProtocol": ("quadkit.contracts.ai.llm", "PromptAssemblerProtocol"),
    "PromptCompressorProtocol": (
        "quadkit.contracts.ai.rag",
        "PromptCompressorProtocol",
    ),
    "SemanticCacheProtocol": ("quadkit.contracts.ai.llm", "SemanticCacheProtocol"),
    "SemanticMemoryProtocol": ("quadkit.contracts.ai", "SemanticMemoryProtocol"),
    "TokenBudget": ("quadkit.contracts.ai.llm", "TokenBudget"),
    "TokenCounterProtocol": ("quadkit.contracts.ai.llm", "TokenCounterProtocol"),
    "DocumentVectorStoreProtocol": (
        "quadkit.contracts.ai.vector",
        "DocumentVectorStoreProtocol",
    ),
    "VectorStoreProtocol": (
        "quadkit.contracts.data.vector.protocols",
        "VectorStoreProtocol",
    ),
    "WorkingMemoryProtocol": ("quadkit.contracts.ai", "WorkingMemoryProtocol"),
    # auth
    "AuthProviderProtocol": ("quadkit.contracts.auth", "AuthProviderProtocol"),
    "AuthenticatedUserProtocol": (
        "quadkit.contracts.auth",
        "AuthenticatedUserProtocol",
    ),
    "AuthorizerProtocol": ("quadkit.contracts.auth", "AuthorizerProtocol"),
    "PasswordHasherProtocol": ("quadkit.contracts.auth", "PasswordHasherProtocol"),
    "TokenManagerProtocol": ("quadkit.contracts.auth", "TokenManagerProtocol"),
    "UserProtocol": ("quadkit.contracts.auth", "UserProtocol"),
    # cache
    "CacheAdminProtocol": ("quadkit.contracts.infra.cache", "CacheAdminProtocol"),
    "CacheBackendProtocol": ("quadkit.contracts.infra.cache", "CacheBackendProtocol"),
    "CacheProviderProtocol": (
        "quadkit.contracts.infra.cache",
        "CacheProviderProtocol",
    ),
    "RedisClientProtocol": ("quadkit.contracts.infra.redis", "RedisClientProtocol"),
    # core
    "AggregateHealthResult": ("quadkit.contracts.core", "AggregateHealthResult"),
    "ConfigProtocol": ("quadkit.contracts.core", "ConfigProtocol"),
    "ClockProtocol": ("quadkit.contracts.core", "ClockProtocol"),
    "ContainerProtocol": ("quadkit.contracts.core", "ContainerProtocol"),
    "ContainerRegistrarProtocol": (
        "quadkit.contracts.core",
        "ContainerRegistrarProtocol",
    ),
    "ContainerResolverProtocol": (
        "quadkit.contracts.core",
        "ContainerResolverProtocol",
    ),
    "GracefulShutdownProtocol": ("quadkit.contracts.core", "GracefulShutdownProtocol"),
    "HealthCheckAggregatorProtocol": (
        "quadkit.contracts.core",
        "HealthCheckAggregatorProtocol",
    ),
    "HealthCheckProtocol": ("quadkit.contracts.core", "HealthCheckProtocol"),
    "HealthCheckRegistryProtocol": (
        "quadkit.contracts.observability.metrics",
        "HealthCheckRegistryProtocol",
    ),
    "HealthCheckResult": ("quadkit.contracts.core", "HealthCheckResult"),
    "HealthStatus": ("quadkit.contracts.core", "HealthStatus"),
    "Duration": ("quadkit.contracts.core", "Duration"),
    "IdGeneratorProtocol": ("quadkit.contracts.core", "IdGeneratorProtocol"),
    "IdStrategy": ("quadkit.contracts.core", "IdStrategy"),
    "JSON": ("quadkit.contracts.core", "JSON"),
    "Lifecycle": ("quadkit.contracts.core", "Lifecycle"),
    "LockStoreProtocol": ("quadkit.contracts.core", "LockStoreProtocol"),
    "Metadata": ("quadkit.contracts.core", "Metadata"),
    "OnApplicationBootstrapProtocol": (
        "quadkit.contracts.core",
        "OnApplicationBootstrapProtocol",
    ),
    "OnApplicationShutdownProtocol": (
        "quadkit.contracts.core",
        "OnApplicationShutdownProtocol",
    ),
    "OnBeforeShutdownProtocol": ("quadkit.contracts.core", "OnBeforeShutdownProtocol"),
    "OnModuleInitProtocol": ("quadkit.contracts.core", "OnModuleInitProtocol"),
    "ProviderPriority": ("quadkit.contracts.core", "ProviderPriority"),
    "ProviderProtocol": ("quadkit.contracts.core", "ProviderProtocol"),
    "Result": ("quadkit.contracts.core", "Result"),
    "AsyncStringSerializerProtocol": (
        "quadkit.contracts.core",
        "AsyncStringSerializerProtocol",
    ),
    "SerializerProtocol": ("quadkit.contracts.core", "SerializerProtocol"),
    "ServiceScope": ("quadkit.contracts.core", "ServiceScope"),
    "TokenPayload": ("quadkit.contracts.core", "TokenPayload"),
    # idempotency
    "IdempotencyMiddlewareProtocol": (
        "quadkit.contracts.core.idempotency",
        "IdempotencyMiddlewareProtocol",
    ),
    "IdempotencyStoreProtocol": (
        "quadkit.contracts.core.idempotency",
        "IdempotencyStoreProtocol",
    ),
    # lock
    "AsyncLockProtocol": ("quadkit.contracts.core.lock", "AsyncLockProtocol"),
    "DistributedLockProtocol": (
        "quadkit.contracts.core.lock",
        "DistributedLockProtocol",
    ),
    "LockInfo": ("quadkit.contracts.core.lock", "LockInfo"),
    "LockManagerProtocol": ("quadkit.contracts.core.lock", "LockManagerProtocol"),
    # validation
    "ValidationError": ("quadkit.contracts.core.validation", "ValidationError"),
    # data
    "ConnectionPoolProtocol": ("quadkit.contracts.data", "ConnectionPoolProtocol"),
    "ConnectionProtocol": ("quadkit.contracts.data", "ConnectionProtocol"),
    "DatabaseProviderProtocol": ("quadkit.contracts.data", "DatabaseProviderProtocol"),
    "DeleteResult": ("quadkit.contracts.data", "DeleteResult"),
    "InsertResult": ("quadkit.contracts.data", "InsertResult"),
    "MigrationManagerProtocol": ("quadkit.contracts.data", "MigrationManagerProtocol"),
    "MigrationRecord": ("quadkit.contracts.data", "MigrationRecord"),
    "QueryLogEntry": ("quadkit.contracts.data", "QueryLogEntry"),
    "QueryLoggerProtocol": ("quadkit.contracts.data", "QueryLoggerProtocol"),
    "QueryResult": ("quadkit.contracts.data", "QueryResult"),
    "ReadOnlyRepositoryProtocol": (
        "quadkit.contracts.data",
        "ReadOnlyRepositoryProtocol",
    ),
    "RepositoryProtocol": ("quadkit.contracts.data", "RepositoryProtocol"),
    "UnitOfWorkProtocol": ("quadkit.contracts.data", "UnitOfWorkProtocol"),
    "UpdateResult": ("quadkit.contracts.data", "UpdateResult"),
    # migrations
    "MigrationRunnerProtocol": (
        "quadkit.contracts.data.sql.migrations",
        "MigrationRunnerProtocol",
    ),
    # aggregates
    "AggregateRootProtocol": (
        "quadkit.contracts.domain.aggregates",
        "AggregateRootProtocol",
    ),
    # events
    "DomainEvent": ("quadkit.contracts.domain.events", "DomainEvent"),
    # specification
    "SpecificationProtocol": (
        "quadkit.contracts.domain.specification",
        "SpecificationProtocol",
    ),
    # state
    "StateStoreProtocol": ("quadkit.contracts.infra.state", "StateStoreProtocol"),
    # events
    "CommandBusProtocol": ("quadkit.contracts.events", "CommandBusProtocol"),
    "DomainEventPublisherProtocol": (
        "quadkit.contracts.events",
        "DomainEventPublisherProtocol",
    ),
    "EventBusProtocol": ("quadkit.contracts.events", "EventBusProtocol"),
    "EventHandlerProtocol": ("quadkit.contracts.events", "EventHandlerProtocol"),
    "EventStoreProtocol": ("quadkit.contracts.events", "EventStoreProtocol"),
    "QueryBusProtocol": ("quadkit.contracts.events", "QueryBusProtocol"),
    # components
    "SecretNotFoundError": (
        "quadkit.contracts.exceptions.components",
        "SecretNotFoundError",
    ),
    # security
    "SecretAccessError": (
        "quadkit.contracts.exceptions.security",
        "SecretAccessError",
    ),
    # events
    "DuplicateHandlerError": (
        "quadkit.contracts.exceptions.events",
        "DuplicateHandlerError",
    ),
    "HandlerNotFoundError": (
        "quadkit.contracts.exceptions.events",
        "HandlerNotFoundError",
    ),
    # mapping
    "ObjectMapperProtocol": ("quadkit.contracts.mapping", "ObjectMapperProtocol"),
    # mcp
    "MCPError": ("quadkit.contracts.mcp", "MCPError"),
    "MCPInitializationError": ("quadkit.contracts.mcp", "MCPInitializationError"),
    "MCPMethodNotFoundError": ("quadkit.contracts.mcp", "MCPMethodNotFoundError"),
    "MCPPromptError": ("quadkit.contracts.mcp", "MCPPromptError"),
    "MCPProtocolError": ("quadkit.contracts.mcp", "MCPProtocolError"),
    "MCPResourceError": ("quadkit.contracts.mcp", "MCPResourceError"),
    "MCPServerProtocol": ("quadkit.contracts.mcp", "MCPServerProtocol"),
    "MCPToolCallError": ("quadkit.contracts.mcp", "MCPToolCallError"),
    "MCPToolProviderProtocol": ("quadkit.contracts.mcp", "MCPToolProviderProtocol"),
    "MCPTransportProtocol": ("quadkit.contracts.mcp", "MCPTransportProtocol"),
    # monitor
    "ProjectionTier": ("quadkit.contracts.monitor", "ProjectionTier"),
    "WebhookSignatureVerifierProtocol": (
        "quadkit.contracts.events",
        "WebhookSignatureVerifierProtocol",
    ),
    # resilience
    "CircuitBreakerConfig": (
        "quadkit.contracts.infra.resilience",
        "CircuitBreakerConfig",
    ),
    "RetryConfig": ("quadkit.contracts.infra.resilience", "RetryConfig"),
    # search
    "SearchEngineProtocol": ("quadkit.contracts.search", "SearchEngineProtocol"),
    # security
    "AsyncSecretStoreProtocol": (
        "quadkit.contracts.security",
        "AsyncSecretStoreProtocol",
    ),
    "HasherProtocol": ("quadkit.contracts.security", "HasherProtocol"),
    "KeyDerivationProtocol": (
        "quadkit.contracts.security",
        "KeyDerivationProtocol",
    ),
    # secrets
    "SecretStoreProtocol": (
        "quadkit.contracts.security.secrets",
        "SecretStoreProtocol",
    ),
    # resources
    "PoolProtocol": ("quadkit.contracts.infra.resources", "PoolProtocol"),
    "PoolManagerProtocol": (
        "quadkit.contracts.infra.resources",
        "PoolManagerProtocol",
    ),
    "PoolStatsProtocol": ("quadkit.contracts.infra.resources", "PoolStatsProtocol"),
    # storage
    "BlobStoreProtocol": ("quadkit.contracts.infra.storage", "BlobStoreProtocol"),
    # tasks
    "JobProtocol": ("quadkit.contracts.infra.tasks", "JobProtocol"),
    "JobStatus": ("quadkit.contracts.infra.tasks", "JobStatus"),
    "TaskExecutorProtocol": ("quadkit.contracts.infra.tasks", "TaskExecutorProtocol"),
    "TaskProviderProtocol": ("quadkit.contracts.infra.tasks", "TaskProviderProtocol"),
    "TaskQueueProtocol": ("quadkit.contracts.infra.tasks", "TaskQueueProtocol"),
    # web
    "CORSPolicyProtocol": ("quadkit.contracts.web", "CORSPolicyProtocol"),
    "ErrorDetail": ("quadkit.contracts.web", "ErrorDetail"),
    "ErrorResponseDTO": ("quadkit.contracts.web", "ErrorResponseDTO"),
    "HttpRequestLoggerProtocol": (
        "quadkit.contracts.web",
        "HttpRequestLoggerProtocol",
    ),
    "PaginatedResponseDTO": ("quadkit.contracts.web", "PaginatedResponseDTO"),
    # workflow
    "SagaProtocol": ("quadkit.contracts.workflow", "SagaProtocol"),
    "SagaManagerProtocol": ("quadkit.contracts.workflow", "SagaManagerProtocol"),
    "WorkflowNodeProtocol": (
        "quadkit.contracts.workflow.protocols",
        "WorkflowNodeProtocol",
    ),
    "AIWorkflowNodeProtocol": (
        "quadkit.contracts.ai.workflow",
        "AIWorkflowNodeProtocol",
    ),
    # audit
    "AuditEntry": ("quadkit.contracts.audit", "AuditEntry"),
    # feature_flags
    "FlagEvaluation": ("quadkit.contracts.feature_flags", "FlagEvaluation"),
    "FlagType": ("quadkit.contracts.feature_flags", "FlagType"),
    "FlagValue": ("quadkit.contracts.feature_flags", "FlagValue"),
    # pagination
    "CursorPage": ("quadkit.contracts.domain.pagination", "CursorPage"),
    "CursorPageProtocol": (
        "quadkit.contracts.domain.pagination",
        "CursorPageProtocol",
    ),
    "OffsetPageProtocol": (
        "quadkit.contracts.domain.pagination",
        "OffsetPageProtocol",
    ),
    # tenancy
    "TenantConfigError": ("quadkit.contracts.tenancy", "TenantConfigError"),
    "TenantConfigProviderProtocol": (
        "quadkit.contracts.tenancy",
        "TenantConfigProviderProtocol",
    ),
    "TenantError": ("quadkit.contracts.tenancy", "TenantError"),
    "TenantInactiveError": ("quadkit.contracts.tenancy", "TenantInactiveError"),
    "TenantInfo": ("quadkit.contracts.tenancy", "TenantInfo"),
    "TenantIsolationStrategyProtocol": (
        "quadkit.contracts.tenancy",
        "TenantIsolationStrategyProtocol",
    ),
    "TenantNotFoundError": ("quadkit.contracts.tenancy", "TenantNotFoundError"),
    "TenantProviderProtocol": ("quadkit.contracts.tenancy", "TenantProviderProtocol"),
    "TenantProvisioningError": (
        "quadkit.contracts.tenancy",
        "TenantProvisioningError",
    ),
    "TenantResolutionContext": (
        "quadkit.contracts.tenancy",
        "TenantResolutionContext",
    ),
    "TenantResolutionError": ("quadkit.contracts.tenancy", "TenantResolutionError"),
    "TenantResolverProtocol": ("quadkit.contracts.tenancy", "TenantResolverProtocol"),
    "TenantSlugConflictError": (
        "quadkit.contracts.tenancy",
        "TenantSlugConflictError",
    ),
    "TenantStatus": ("quadkit.contracts.tenancy", "TenantStatus"),
    "TenantSuspendedError": ("quadkit.contracts.tenancy", "TenantSuspendedError"),
}


def __getattr__(name: str) -> Any:
    """Lazy-load public symbols on first access."""
    if name in _LAZY_IMPORTS:
        import importlib

        module_path, attr_name = _LAZY_IMPORTS[name]
        module = importlib.import_module(module_path)
        value = getattr(module, attr_name)
        globals()[name] = value
        return value
    if name in _SUBMODULE_NAMES:
        import importlib

        return importlib.import_module(f"quadkit.contracts.{name}")
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(__all__) | set(_LAZY_IMPORTS.keys()))


__all__ = list(_LAZY_IMPORTS)
