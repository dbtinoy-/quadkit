"""Registry modules for Quadkit CLI.

This package provides registry patterns for:
- Database backends (database.py)
- Health checks (health.py)
- Config validators (config.py)
- Server backends (server.py)
- Project templates (template.py)
- Providers (provider.py)
- Code generators (generator.py)
- Task runners (task.py)
- Inspectors (inspect.py)
- Formatters (formatter.py)
- Environments (environment.py)
- Hooks (hook.py)
- Migrations (migration.py)
- Serializers (serializer.py)
- Watchers (watcher.py)
- Completions (completion.py)
- Presets (presets.py)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    # Re-exported names, for type checkers only. At runtime every name
    # resolves lazily via __getattr__ (PEP 562) so importing this package
    # does not load all seventeen registry modules (plans/09172026 C-02).
    from quadkit.cli.registry.completion import (
        BashCompletionGenerator,
        CompletionGenerator,
        CompletionRegistry,
        FishCompletionGenerator,
        PowerShellCompletionGenerator,
        ZshCompletionGenerator,
        generate_completion,
    )
    from quadkit.cli.registry.config import (
        AuthConfigValidator,
        ConfigValidator,
        ConfigValidatorRegistry,
        DatabaseConfigValidator,
        EnvironmentVariablesValidator,
        ProductionValidator,
        RequiredFieldsValidator,
        SecretValidationValidator,
        ValidationIssue,
        ValidationSeverity,
        has_errors,
        validate_config,
    )
    from quadkit.cli.registry.database import (
        DatabaseBackend,
        DatabaseConnection,
        DatabaseRegistry,
        MySQLBackend,
        PostgreSQLBackend,
        SQLiteBackend,
        create_database_connection,
    )
    from quadkit.cli.registry.environment import (
        DevelopmentEnvironment,
        Environment,
        EnvironmentConfig,
        EnvironmentManager,
        EnvironmentRegistry,
        ProductionEnvironment,
        StagingEnvironment,
        TestEnvironment,
    )
    from quadkit.cli.registry.formatter import (
        FormatOptions,
        FormatterRegistry,
        JSONFormatter,
        OutputFormatter,
        SimpleFormatter,
        TableFormatter,
        YAMLFormatter,
        format_output,
    )
    from quadkit.cli.registry.generator import (
        CodeGenerator,
        GeneratorAdapter,
        GeneratorRegistry,
        GeneratorResult,
    )
    from quadkit.cli.registry.health import (
        CheckResult,
        CheckStatus,
        ConfigFileCheck,
        DependenciesCheck,
        DockerCheck,
        GitCheck,
        HealthCheck,
        HealthCheckRegistry,
        PackageManagerCheck,
        ProjectStructureCheck,
        PythonVersionCheck,
        RequiredToolsCheck,
        run_health_checks,
    )
    from quadkit.cli.registry.hook import (
        ErrorHandlingHook,
        Hook,
        HookContext,
        HookExecutor,
        HookHandler,
        HookPhase,
        HookRegistry,
        HookResult,
        LoggingHook,
        TimingHook,
        ValidationHook,
        create_validation_hook,
    )
    from quadkit.cli.registry.inspect import (
        ContainerInspector,
        DependenciesInspector,
        EventsInspector,
        InspectionResult,
        Inspector,
        InspectorRegistry,
        MiddlewareInspector,
        ProvidersInspector,
        RoutesInspector,
        TasksInspector,
    )
    from quadkit.cli.registry.presets import (
        FullStackPreset,
        GraphQLPreset,
        MicroservicePreset,
        MinimalPreset,
        Preset,
        PresetDefinition,
        PresetRegistry,
        WebAPIPreset,
        WorkerPreset,
    )
    from quadkit.cli.registry.provider import (
        AdminProvider,
        AIProvider,
        AuthProvider,
        CacheProvider,
        CommonProvider,
        ConnectProvider,
        DatabaseService,
        EventsProvider,
        GraphQLProvider,
        MessagingProvider,
        MonitoringProvider,
        MonitorProvider,
        NotificationProvider,
        Provider,
        ProviderInfo,
        ProviderInstaller,
        ProviderRegistry,
        QueueProvider,
        ResilienceProvider,
        SearchProvider,
        StorageProvider,
        TasksProvider,
        TestingProvider,
        WebProvider,
    )
    from quadkit.cli.registry.secrets import (
        SecretBackend,
        SecretInfo,
        SecretsRegistry,
        generate_api_key,
        generate_jwt_secret,
        generate_secret,
    )
    from quadkit.cli.registry.server import (
        GranianBackend,
        GunicornBackend,
        HypercornBackend,
        ServerBackend,
        ServerConfig,
        ServerManager,
        ServerRegistry,
        UvicornBackend,
        discover_entry_point,
    )
    from quadkit.cli.registry.task import (
        MypyRunner,
        PytestRunner,
        RuffRunner,
        TaskResult,
        TaskRunner,
        TaskRunnerRegistry,
    )
    from quadkit.cli.registry.telemetry import (
        TelemetryBackend,
        TelemetryEvent,
        TelemetryRegistry,
        disable_telemetry,
        enable_telemetry,
        get_telemetry_status,
    )
    from quadkit.cli.registry.template import (
        FullStackTemplate,
        GraphQLTemplate,
        MinimalTemplate,
        ProjectBuilder,
        ProjectTemplate,
        TemplateConfig,
        TemplateRegistry,
        WebAPITemplate,
        WorkerTemplate,
    )
    from quadkit.cli.registry.version import (
        VersionInfo,
        VersionRegistry,
        VersionSource,
        get_all_versions,
        get_version,
    )

__all__ = [
    "AIProvider",
    "AdminProvider",
    "AuthConfigValidator",
    "AuthProvider",
    "CacheProvider",
    "CheckResult",
    "CheckStatus",
    "CodeGenerator",
    "CommonProvider",
    "CompletionGenerator",
    "CompletionRegistry",
    "ConfigFileCheck",
    "ConfigValidator",
    "ConfigValidatorRegistry",
    "ConnectProvider",
    "ContainerInspector",
    "DatabaseBackend",
    "DatabaseConfigValidator",
    "DatabaseConnection",
    "DatabaseRegistry",
    "DatabaseService",
    "DependenciesCheck",
    "DependenciesInspector",
    "DockerCheck",
    "Environment",
    "EnvironmentConfig",
    "EnvironmentManager",
    "EnvironmentRegistry",
    "EnvironmentVariablesValidator",
    "ErrorHandlingHook",
    "EventsInspector",
    "EventsProvider",
    "FormatOptions",
    "FormatterRegistry",
    "GeneratorAdapter",
    "GeneratorRegistry",
    "GeneratorResult",
    "GitCheck",
    "GraphQLProvider",
    "HealthCheck",
    "HealthCheckRegistry",
    "Hook",
    "HookContext",
    "HookExecutor",
    "HookHandler",
    "HookPhase",
    "HookRegistry",
    "HookResult",
    "InspectionResult",
    "Inspector",
    "InspectorRegistry",
    "LoggingHook",
    "MessagingProvider",
    "MiddlewareInspector",
    "MonitorProvider",
    "MonitoringProvider",
    "NotificationProvider",
    "OutputFormatter",
    "PackageManagerCheck",
    "Preset",
    "PresetDefinition",
    "PresetRegistry",
    "ProductionValidator",
    "ProjectBuilder",
    "ProjectStructureCheck",
    "ProjectTemplate",
    "Provider",
    "ProviderInfo",
    "ProviderInstaller",
    "ProviderRegistry",
    "ProvidersInspector",
    "PythonVersionCheck",
    "QueueProvider",
    "RequiredFieldsValidator",
    "RequiredToolsCheck",
    "ResilienceProvider",
    "RoutesInspector",
    "SearchProvider",
    "SecretBackend",
    "SecretInfo",
    "SecretValidationValidator",
    "SecretsRegistry",
    "ServerBackend",
    "ServerConfig",
    "ServerManager",
    "ServerRegistry",
    "StorageProvider",
    "TaskResult",
    "TaskRunner",
    "TaskRunnerRegistry",
    "TasksInspector",
    "TasksProvider",
    "TelemetryBackend",
    "TelemetryEvent",
    "TelemetryRegistry",
    "TemplateConfig",
    "TemplateRegistry",
    "TestingProvider",
    "TimingHook",
    "ValidationHook",
    "ValidationIssue",
    "ValidationSeverity",
    "VersionInfo",
    "VersionRegistry",
    "VersionSource",
    "WebProvider",
    "create_database_connection",
    "create_validation_hook",
    "disable_telemetry",
    "discover_entry_point",
    "enable_telemetry",
    "format_output",
    "generate_api_key",
    "generate_completion",
    "generate_jwt_secret",
    "generate_secret",
    "get_all_versions",
    "get_telemetry_status",
    "get_version",
    "has_errors",
    "run_health_checks",
    "validate_config",
]


from quadkit.cli.registry._lazy_exports import LAZY_IMPORTS as _LAZY_IMPORTS


def __getattr__(name: str) -> Any:
    """Resolve registry re-exports lazily (PEP 562)."""
    module_path = _LAZY_IMPORTS.get(name)
    if module_path is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from importlib import import_module

    value = getattr(import_module(module_path), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(_LAZY_IMPORTS))
