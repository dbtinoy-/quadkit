"""MCP provider for Quadkit dependency injection."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from quadkit.ai.mcp.config import MCPConfig
from quadkit.ai.mcp.di.provider_connectors import (
    _ConnectorResourceBundle,
    _ConnectorToolBundle,
    boot_connectors,
)
from quadkit.ai.mcp.exceptions import MCPInitializationError
from quadkit.ai.mcp.server import MCPServer
from quadkit.ai.mcp.server.handlers import (
    LoggingHandler,
    PromptHandler,
    ResourceHandler,
    SamplingHandler,
    ToolHandler,
)
from quadkit.ai.mcp.transport import SSETransport, StdioTransport
from quadkit.contracts import (
    ProviderPriority,
)
from quadkit.contracts.core.health import HealthCheckResult, HealthStatus
from quadkit.contracts.mcp.protocols import MCPAuthorizerProtocol
from quadkit.di.provider import Provider
from quadkit.logging import (
    get_logger,
)

if TYPE_CHECKING:
    from quadkit.contracts.core.di import (
        BootContainerProtocol,
        ContainerRegistrarProtocol,
    )

logger = get_logger(__name__)


class MCPProvider(Provider):
    name = "mcp"
    priority = ProviderPriority.PRESENTATION
    config_key: str | None = "ai_mcp"
    config_model: type | None = MCPConfig

    """Provider for MCP server components.

    Registers MCP server, handlers, and transports with the DI container.
    When ``MCPConfig.client_stdio_command`` or ``MCPConfig.client_url`` is
    set, an :class:`~quadkit.ai.mcp.client.MCPClient` is also registered.

    When ``controllers`` is provided (typically set by ``MCPModule``), the
    controller instances are registered as tool/resource/prompt providers
    before the handlers are wired up.
    """

    def __init__(
        self,
        config: MCPConfig | None = None,
        controllers: list[type] | None = None,
        services: list[type] | None = None,
        include_methods: list[str] | None = None,
        enable_streaming: bool = True,
        **provider_kwargs: Any,
    ) -> None:
        super().__init__()
        self._requested_config = config
        self._config = config or MCPConfig()
        self._controllers: list[type] = controllers or []
        self._services: list[type] = services or []
        self._include_methods: list[str] | None = include_methods
        self._enable_streaming = enable_streaming
        self._managed_transports: list[StdioTransport | SSETransport] = []
        self._managed_client: Any | None = None

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        """Register MCPConfig with the DI container."""
        self._config = self._requested_config or (
            self.config
            if isinstance(getattr(self, "config", None), MCPConfig)
            else self._config
        )
        container.singleton(MCPConfig, self._config)

    async def boot(self, container: BootContainerProtocol) -> None:
        """Wire up all MCP components using the resolved container."""
        if not self._config.enabled:
            return

        if self._controllers:
            await self._boot_controller_providers(container)
        if self._services:
            await self._boot_service_providers(container)
        await self._boot_skill_bridge(container)
        await self._boot_connectors(container)
        await self._boot_handlers(container)
        await self._boot_server(container)
        self._boot_transports(container)
        await self._boot_client(container)

    async def _boot_controller_providers(
        self, container: BootContainerProtocol
    ) -> None:
        """Instantiate MCPController classes and register compound providers.

        Controllers are resolved via the DI container when possible so that
        constructor dependencies are injected automatically.
        """
        from quadkit.ai.mcp.controllers import (
            ControllerPromptProvider,
            ControllerResourceProvider,
            ControllerToolProvider,
            MCPController,
        )

        instances: list[MCPController] = []
        for ctrl_class in self._controllers:
            try:
                instance: MCPController = await container.resolve(ctrl_class)
            except Exception as exc:  # noqa: BLE001 — boot wraps any resolution failure as MCPInitializationError
                raise MCPInitializationError(
                    message=f"Failed to resolve MCP controller: {ctrl_class.__name__}"
                ) from exc
            instances.append(instance)
            logger.debug("mcp_controller_registered", controller=ctrl_class.__name__)

        container.singleton(ControllerToolProvider, ControllerToolProvider(instances))
        container.singleton(
            ControllerResourceProvider, ControllerResourceProvider(instances)
        )
        container.singleton(
            ControllerPromptProvider, ControllerPromptProvider(instances)
        )

    async def _boot_service_providers(self, container: BootContainerProtocol) -> None:
        """Resolve service classes and register a ServiceToolProvider."""
        from quadkit.ai.mcp.controllers import ServiceToolProvider

        instances: list[object] = []
        for svc_class in self._services:
            try:
                instance: object = await container.resolve(svc_class)
            except Exception as exc:  # noqa: BLE001 — boot wraps any resolution failure as MCPInitializationError
                raise MCPInitializationError(
                    message=f"Failed to resolve MCP service: {svc_class.__name__}"
                ) from exc
            instances.append(instance)
            logger.debug("mcp_service_registered", service_type=svc_class.__name__)

        container.singleton(
            ServiceToolProvider,
            ServiceToolProvider.from_services(instances, self._include_methods),
        )

    async def _boot_skill_bridge(self, container: BootContainerProtocol) -> None:
        """Register SkillToolAdapter if the optional provider is available.

        When ``SkillRegistryProtocol`` and ``SkillExecutorProtocol`` are
        registered in the container (by ``the optional provider``), a
        :class:`~quadkit.ai.mcp.adapters.skill_adapter.SkillToolAdapter` is
        created and registered so that skills are exposed as MCP tools.
        """
        skill_registry = None
        skill_executor = None
        try:
            from quadkit.contracts.ai.skills import (
                SkillExecutorProtocol,
                SkillRegistryProtocol,
            )

            skill_registry = await container.resolve(SkillRegistryProtocol)
            skill_executor = await container.resolve(SkillExecutorProtocol)
        except Exception:  # noqa: BLE001 — skills registration is optional
            logger.debug("mcp_skills_not_available")
            return

        from quadkit.ai.mcp.adapters.skill_adapter import SkillToolAdapter

        adapter = SkillToolAdapter(
            skill_registry=skill_registry,
            skill_executor=skill_executor,
        )
        container.singleton(SkillToolAdapter, adapter)
        logger.info("mcp_skill_bridge_registered")

    async def _boot_connectors(self, container: BootContainerProtocol) -> None:
        """Instantiate and register built-in connectors from ``MCPConfig.connectors``."""
        await boot_connectors(self._config, container)

    async def _boot_handlers(self, container: BootContainerProtocol) -> None:
        """Register MCP handlers, wiring in controller providers when available.

        When ``MCPModule(controllers=[...])`` has already registered
        ``ControllerToolProvider`` / ``ControllerResourceProvider`` /
        ``ControllerPromptProvider`` in the container, those are passed to the
        handlers so that ``@tool``/``@resource``/``@prompt`` decorated methods
        are automatically exposed.  Falls back to empty (no-op) handlers when
        no controllers are configured.
        """
        from quadkit.ai.mcp.controllers import (
            ControllerPromptProvider,
            ControllerResourceProvider,
            ControllerToolProvider,
        )

        tool_provider: Any | None = await container.resolve_optional(
            ControllerToolProvider
        )
        resource_provider: Any | None = await container.resolve_optional(
            ControllerResourceProvider
        )
        prompt_provider: Any | None = await container.resolve_optional(
            ControllerPromptProvider
        )

        # Merge service tools with controller tools when both exist
        service_tool_provider = None
        try:
            from quadkit.ai.mcp.controllers import ServiceToolProvider

            service_tool_provider = await container.resolve_optional(
                ServiceToolProvider
            )
        except (ImportError, AttributeError):
            pass

        if tool_provider is not None and service_tool_provider is not None:
            from quadkit.ai.mcp.controllers import _CombinedToolProvider

            tool_provider = _CombinedToolProvider(
                [tool_provider, service_tool_provider]
            )
        elif service_tool_provider is not None:
            tool_provider = service_tool_provider

        # Merge built-in connector tools / resources when any connectors are configured
        connector_tool_bundle = await container.resolve_optional(_ConnectorToolBundle)
        connector_resource_bundle = await container.resolve_optional(
            _ConnectorResourceBundle
        )
        if connector_tool_bundle is not None:
            from quadkit.ai.mcp.controllers import _CombinedToolProvider

            tool_provider = _CombinedToolProvider(
                [p for p in [tool_provider, connector_tool_bundle] if p is not None]
            )
        if connector_resource_bundle is not None:
            from quadkit.ai.mcp.controllers import _CombinedResourceProvider

            resource_provider = _CombinedResourceProvider(
                [
                    p
                    for p in [resource_provider, connector_resource_bundle]
                    if p is not None
                ]
            )

        tool_handler = ToolHandler(tool_provider)
        resource_handler = ResourceHandler(resource_provider)
        prompt_handler = PromptHandler(prompt_provider)

        container.singleton(ToolHandler, tool_handler)
        container.singleton(ResourceHandler, resource_handler)
        container.singleton(PromptHandler, prompt_handler)

        # Optional: sampling handler (requires an LLM client in the container)
        try:
            from quadkit.contracts.ai.llm import LLMClientProtocol

            llm_client = await container.resolve_optional(LLMClientProtocol)
            if llm_client is not None:
                sampling_handler = SamplingHandler(llm=llm_client)
                container.singleton(SamplingHandler, sampling_handler)
                logger.info("mcp_sampling_handler_registered")
        except (ImportError, AttributeError):
            pass

        # Always register a logging handler
        logging_handler = LoggingHandler()
        container.singleton(LoggingHandler, logging_handler)

        # G41: Optional observability wrapping
        try:
            from quadkit.ai.mcp.server.observability import (
                ObservableResourceHandler,
                ObservableToolHandler,
            )
            from quadkit.contracts.observability.ai import AIMetricsProtocol

            metrics = await container.resolve_optional(AIMetricsProtocol)
            if metrics is not None:
                observable_tool = ObservableToolHandler(tool_handler, metrics)
                observable_resource = ObservableResourceHandler(
                    resource_handler, metrics
                )
                container.singleton(ToolHandler, observable_tool)
                container.singleton(ResourceHandler, observable_resource)
                logger.info("mcp_observability_wrapping_registered")
        except (ImportError, AttributeError):
            pass

        self._handlers_registered = True

    async def _boot_server(self, container: BootContainerProtocol) -> None:
        """Register MCP server."""
        tool_handler = await container.resolve(ToolHandler)
        resource_handler = await container.resolve(ResourceHandler)
        prompt_handler = await container.resolve(PromptHandler)
        sampling_handler = await container.resolve_optional(SamplingHandler)
        logging_handler = await container.resolve_optional(LoggingHandler)
        authorizer = await container.resolve_optional(MCPAuthorizerProtocol)

        server = MCPServer(
            name=self._config.server_name,
            version=self._config.server_version,
            tool_handler=tool_handler,
            resource_handler=resource_handler,
            prompt_handler=prompt_handler,
            sampling_handler=sampling_handler,
            logging_handler=logging_handler,
            authorizer=authorizer,
            allow_unauthenticated=self._config.allow_unauthenticated,
        )

        registrar = cast("ContainerRegistrarProtocol", container)
        registrar.singleton(MCPServer, server)

    def _boot_transports(self, container: ContainerRegistrarProtocol) -> None:
        """Register MCP transport singletons."""
        stdio_transport = StdioTransport()
        sse_transport = SSETransport()

        container.singleton(StdioTransport, stdio_transport)
        container.singleton(SSETransport, sse_transport)
        self._managed_transports = [stdio_transport, sse_transport]

    async def shutdown(self) -> None:
        """Clean up MCP provider resources."""
        for transport in self._managed_transports:
            try:
                await transport.stop()
            except Exception as exc:  # noqa: BLE001 — best-effort client start must not raise
                logger.warning(
                    "mcp_transport_stop_failed",
                    transport=type(transport).__name__,
                    error_type=type(exc).__name__,
                )

        self._managed_transports.clear()

        if self._managed_client is not None:
            try:
                await self._managed_client.disconnect()
            except Exception as exc:  # noqa: BLE001 — client disconnect is best-effort
                logger.warning(
                    "mcp_client_disconnect_failed", error_type=type(exc).__name__
                )
            self._managed_client = None

        logger.info("mcp_provider_shutdown_complete")

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Return a health check result for this provider.

        Args:
            timeout: Maximum seconds to wait for health response.

        Returns:
            A :class:`~quadkit.contracts.core.health.HealthCheckResult`
            reflecting the current MCP provider state.
        """
        if self._managed_client is not None:
            is_connected = getattr(self._managed_client, "is_connected", None)
            if (callable(is_connected) and not is_connected()) or (
                isinstance(is_connected, bool) and not is_connected
            ):
                return HealthCheckResult(
                    component=self.name,
                    status=HealthStatus.DEGRADED,
                    details={"reason": "MCP client disconnected"},
                )
        return HealthCheckResult(
            component=self.name,
            status=HealthStatus.HEALTHY,
            details={"status": "operational"},
        )

    async def _boot_client(self, container: BootContainerProtocol) -> None:
        """Register MCPClient if client configuration is present."""
        from quadkit.ai.mcp.client.core import (
            MCPClient,
            SSEClientTransport,
            StdioClientTransport,
        )

        self._managed_client = None

        if self._config.client_stdio_command:
            stdio_client_transport = StdioClientTransport(
                self._config.client_stdio_command,
                startup_timeout=self._config.request_timeout,
            )
            client = MCPClient(
                stdio_client_transport, request_timeout=self._config.request_timeout
            )
            registrar = cast("ContainerRegistrarProtocol", container)
            registrar.singleton(MCPClient, client)
            self._managed_client = client
            logger.info(
                "mcp_client_registered",
                mode="stdio",
                command=self._config.client_stdio_command[0],
            )
        elif self._config.client_url:
            sse_client_transport = SSEClientTransport(
                self._config.client_url,
                request_timeout=self._config.request_timeout,
            )
            client = MCPClient(
                sse_client_transport, request_timeout=self._config.request_timeout
            )
            registrar = cast("ContainerRegistrarProtocol", container)
            registrar.singleton(MCPClient, client)
            self._managed_client = client
            logger.info("mcp_client_registered", mode="sse")


__all__ = ["MCPProvider"]
