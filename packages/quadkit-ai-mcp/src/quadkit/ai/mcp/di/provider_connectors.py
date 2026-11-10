"""Connector bootstrapping for the MCP DI provider.

Builds built-in connector instances from ``MCPConfig.connectors`` and
registers them under sentinel bundle types that :meth:`MCPProvider._boot_handlers`
later merges with controller/service providers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from quadkit.logging import (
    get_logger,
)

if TYPE_CHECKING:
    from quadkit.ai.mcp.config import MCPConfig
    from quadkit.contracts.core.di import BootContainerProtocol

logger = get_logger(__name__)


class _ConnectorToolBundle:
    """Sentinel DI type: combined tool provider for all built-in connectors."""


class _ConnectorResourceBundle:
    """Sentinel DI type: combined resource provider for all built-in connectors."""


async def boot_connectors(config: MCPConfig, container: BootContainerProtocol) -> None:
    """Instantiate and register built-in connectors from ``config.connectors``.

    Each connector that has sufficient configuration is instantiated and
    collected into :class:`_ConnectorToolBundle` and
    :class:`_ConnectorResourceBundle` sentinel types.  The handler boot
    phase then picks them up and merges them with the controller/service
    providers.

    Args:
        config: Resolved MCP configuration holding connector settings.
        container: Container used to resolve the optional database provider
            required by the SQL connector.
    """
    from quadkit.ai.mcp.connectors import (
        FilesystemConnector,
        GitHubConnector,
        GoogleDriveConnector,
        SlackConnector,
        SQLConnector,
        WebFetchConnector,
        WebSearchConnector,
    )
    from quadkit.ai.mcp.controllers import (
        _CombinedResourceProvider,
        _CombinedToolProvider,
    )

    cfg = config.connectors
    connectors: list[object] = []

    if cfg.filesystem.root_dir:
        connectors.append(
            FilesystemConnector(
                root_dir=cfg.filesystem.root_dir,
                read_only=cfg.filesystem.read_only,
            )
        )
        logger.info("mcp_connector_registered", connector="filesystem")

    if cfg.github.token:
        connectors.append(GitHubConnector(token=cfg.github.token))
        logger.info("mcp_connector_registered", connector="github")

    if cfg.web_fetch.enabled:
        connectors.append(
            WebFetchConnector(
                max_content_bytes=cfg.web_fetch.max_content_bytes,
            )
        )
        logger.info("mcp_connector_registered", connector="web_fetch")

    if cfg.web_search.api_key:
        connectors.append(
            WebSearchConnector(
                provider=cfg.web_search.provider,
                api_key=cfg.web_search.api_key,
                max_results=cfg.web_search.max_results,
            )
        )
        logger.info("mcp_connector_registered", connector="web_search")

    if cfg.slack.bot_token:
        connectors.append(
            SlackConnector(
                bot_token=cfg.slack.bot_token,
                max_messages=cfg.slack.max_messages,
            )
        )
        logger.info("mcp_connector_registered", connector="slack")

    if cfg.google_drive.service_account_json:
        connectors.append(
            GoogleDriveConnector(
                service_account_json=cfg.google_drive.service_account_json,
                impersonated_email=cfg.google_drive.impersonated_email,
            )
        )
        logger.info("mcp_connector_registered", connector="google_drive")

    if cfg.sql.dsn:
        try:
            from quadkit.contracts.data import DatabaseProviderProtocol

            db_provider = await container.resolve_optional(DatabaseProviderProtocol)
            if db_provider is not None:
                connectors.append(
                    SQLConnector(
                        db=db_provider,
                        allowed_tables=cfg.sql.allowed_tables,
                        read_only=cfg.sql.read_only,
                    )
                )
                logger.info("mcp_connector_registered", connector="sql")
        except Exception:  # noqa: BLE001 — sql connector registration is optional
            logger.debug("mcp_sql_connector_skipped_no_db_provider")

    if not connectors:
        return

    tool_bundle = _CombinedToolProvider(connectors)
    resource_bundle = _CombinedResourceProvider(connectors)
    container.singleton(_ConnectorToolBundle, tool_bundle)
    container.singleton(_ConnectorResourceBundle, resource_bundle)
