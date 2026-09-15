"""Admin contracts — protocols and types for the admin contributor system."""

from __future__ import annotations

from quadkit.contracts.admin.action_hooks import ActionHookProtocol, HasActionHooks
from quadkit.contracts.admin.audit_entry import AuditEntry, AuditOutcome
from quadkit.contracts.admin.audit_logger import AdminAuditLoggerProtocol
from quadkit.contracts.admin.cache_provider import CacheProviderProtocol
from quadkit.contracts.admin.contributor import BaseAdminContributor
from quadkit.contracts.admin.cqrs import AdminCommand, AdminQuery
from quadkit.contracts.admin.errors import (
    AdminError,
    HealthCheckNotFoundError,
    WidgetNotFoundError,
)
from quadkit.contracts.admin.health_payload import HealthCheckPayload
from quadkit.contracts.admin.operations import (
    AdminSearchableProtocol,
    AggregatableProtocol,
    AuditableProtocol,
    BulkOperationsProtocol,
    CacheAwareProtocol,
    ExportableProtocol,
    RelationLoaderProtocol,
    TransactionalProtocol,
    ValidatableProtocol,
)
from quadkit.contracts.admin.page_content import PageContent, PaginationContent
from quadkit.contracts.admin.page_handler import (
    AdminPageHandlerProtocol,
    ManagementPageHandler,
)
from quadkit.contracts.admin.pii_redactor import PiiRedactorProtocol
from quadkit.contracts.admin.principal import (
    AdminPrincipal,
    AdminPrincipalProviderProtocol,
)
from quadkit.contracts.admin.protocols import (
    AdminContributorProtocol,
    AdminContributorRegistryProtocol,
    AdminDashboardProtocol,
)
from quadkit.contracts.admin.repository import AdminRepositoryProtocol
from quadkit.contracts.admin.route_spec import AdminRouteSpec
from quadkit.contracts.admin.stats import (
    CacheStatsProtocol,
    DlqStatsProtocol,
    HealthOverviewProtocol,
    MetricsReadbackProtocol,
    NamedHealthCheckProtocol,
    QueueStatsProtocol,
    SessionCountProtocol,
)
from quadkit.contracts.admin.types import (
    AdminActionDefinition,
    AdminHealthDefinition,
    DashboardWidgetDefinition,
    ManagementPageDefinition,
    NavigationContribution,
    PageCategory,
    PageFilterField,
    SettingsPanelDefinition,
    WidgetCategory,
    WidgetParams,
    WidgetSize,
    WidgetViewModel,
)
from quadkit.contracts.admin.widget_content import (
    ChartContent,
    ChartPoint,
    EmptyContent,
    MessageContent,
    Stat,
    StatContent,
    TableCell,
    TableContent,
    Tone,
    WidgetContent,
    WidgetKind,
)
from quadkit.contracts.admin.widget_protocols import WidgetHandlerProtocol
from quadkit.contracts.data.data_source import DataSourceProtocol

__all__ = [
    "ActionHookProtocol",
    "AdminActionDefinition",
    "AdminAuditLoggerProtocol",
    "AdminCommand",
    "AdminContributorProtocol",
    "AdminContributorRegistryProtocol",
    "AdminDashboardProtocol",
    "AdminError",
    "AdminHealthDefinition",
    "AdminPageHandlerProtocol",
    "AdminPrincipal",
    "AdminPrincipalProviderProtocol",
    "AdminQuery",
    "AdminRepositoryProtocol",
    "AdminRouteSpec",
    "AdminSearchableProtocol",
    "AggregatableProtocol",
    "AuditEntry",
    "AuditOutcome",
    "AuditableProtocol",
    "BaseAdminContributor",
    "BulkOperationsProtocol",
    "CacheAwareProtocol",
    "CacheProviderProtocol",
    "CacheStatsProtocol",
    "ChartContent",
    "ChartPoint",
    "DashboardWidgetDefinition",
    "DataSourceProtocol",
    "DlqStatsProtocol",
    "EmptyContent",
    "ExportableProtocol",
    "HasActionHooks",
    "HealthCheckNotFoundError",
    "HealthCheckPayload",
    "HealthOverviewProtocol",
    "ManagementPageDefinition",
    "ManagementPageHandler",
    "MessageContent",
    "MetricsReadbackProtocol",
    "NamedHealthCheckProtocol",
    "NavigationContribution",
    "PageCategory",
    "PageContent",
    "PageFilterField",
    "PaginationContent",
    "PiiRedactorProtocol",
    "QueueStatsProtocol",
    "RelationLoaderProtocol",
    "SessionCountProtocol",
    "SettingsPanelDefinition",
    "Stat",
    "StatContent",
    "TableCell",
    "TableContent",
    "Tone",
    "TransactionalProtocol",
    "ValidatableProtocol",
    "WidgetCategory",
    "WidgetContent",
    "WidgetHandlerProtocol",
    "WidgetKind",
    "WidgetNotFoundError",
    "WidgetParams",
    "WidgetSize",
    "WidgetViewModel",
]
