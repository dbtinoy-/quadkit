"""Admin contract types — shared value types for the admin contributor system.

These frozen dataclasses cross package boundaries and are used by any
quadkit extension that contributes admin dashboard surfaces.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

from quadkit.contracts.admin.route_spec import AdminRouteSpec
from quadkit.contracts.admin.widget_content import WidgetContent, WidgetKind

if TYPE_CHECKING:
    from quadkit.contracts.admin.page_handler import AdminPageHandlerProtocol


class WidgetSize(StrEnum):
    """Dashboard widget size."""

    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
    FULL = "full"


class WidgetCategory(StrEnum):
    """Dashboard widget category for grouping."""

    HEALTH = "health"
    METRICS = "metrics"
    ACTIVITY = "activity"
    RESOURCES = "resources"
    CUSTOM = "custom"


class PageCategory(StrEnum):
    """Management page category."""

    INFRASTRUCTURE = "infrastructure"
    SECURITY = "security"
    AI = "ai"
    DATA = "data"
    MONITORING = "monitoring"
    CONFIGURATION = "configuration"


@dataclass(frozen=True)
class DashboardWidgetDefinition:
    """Definition for a dashboard widget contributed by a package.

    The ``render_endpoint`` is an HTMX endpoint that the dashboard shell
    will fetch via ``hx-get``.  Each contributor owns its own rendering.
    """

    name: str
    title: str
    contributor: str
    render_endpoint: str
    view_kind: WidgetKind
    size: WidgetSize = WidgetSize.MEDIUM
    category: WidgetCategory = WidgetCategory.CUSTOM
    refresh_interval_seconds: int = 30
    order: int = 100
    permission: str | None = None
    icon: str | None = None
    description: str = ""
    live_resource_types: tuple[str, ...] = ()


@dataclass(frozen=True)
class NavigationContribution:
    """Navigation entry contributed by a package."""

    label: str
    url: str
    icon: str = "box"
    group: str = "framework"
    order: int = 100
    permission: str | None = None
    badge_endpoint: str | None = None
    #: Short sentence describing what this area is for, shown on cluster
    #: landing pages. Defaults to empty so existing contributors are
    #: unaffected; the renderer falls back to generic copy when unset.
    #: Owned by the contributing package because only it knows what its
    #: own area does -- the alternative is the admin maintaining a
    #: hardcoded lookup that silently goes stale as areas are added.
    description: str = ""
    children: tuple[NavigationContribution, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class PageFilterField:
    """Schema field for a page-level dashboard filter.

    Mirrors the admin-side ``ConfigField`` shape, but lives here because it
    crosses the contributor boundary: ``ManagementPageDefinition`` carries a
    filter schema that contributor packages declare.
    """

    name: str
    type: str  # "select" | "number" | "text" | "boolean"
    label: str
    options: tuple[tuple[str, str], ...] = ()  # (value, display_label) for select
    default: str | int | bool | None = None
    description: str = ""


@dataclass(frozen=True)
class ManagementPageDefinition:
    """Full management page contributed by a package.

    The ``handler`` is a dotted path to an async handler function,
    resolved at boot time to avoid import coupling.
    """

    name: str
    title: str
    contributor: str
    route_path: str
    handler: str | AdminPageHandlerProtocol
    category: PageCategory = PageCategory.INFRASTRUCTURE
    icon: str = "settings"
    permission: str | None = None
    description: str = ""
    order: int = 100
    filters: tuple[PageFilterField, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class SettingsPanelDefinition:
    """Settings panel contributed by a package."""

    name: str
    title: str
    contributor: str
    route_path: str
    handler: str | AdminPageHandlerProtocol
    icon: str = "sliders"
    category: str = "General"
    order: int = 100
    permission: str | None = None


@dataclass(frozen=True)
class AdminHealthDefinition:
    """Health check to surface in the admin dashboard."""

    name: str
    contributor: str
    component: str
    check_endpoint: str | None = None
    icon: str = "heart-pulse"
    description: str = ""
    permission: str | None = None


@dataclass(frozen=True)
class ActionParameterField:
    """A single parameter accepted by an admin action handler.

    Used for auto-generated action forms and server-side input validation.
    """

    name: str
    type_hint: str  # string repr e.g. "str", "int", "bool", "list[str]"
    required: bool = True
    default: object | None = None
    description: str = ""
    choices: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ActionParameterSchema:
    """Schema describing the parameter surface of an admin action.

    Enables auto-generated action forms in the admin UI and server-side
    validation before the handler is called.
    """

    fields: tuple[ActionParameterField, ...]
    description: str = ""


@dataclass(frozen=True)
class AdminActionDefinition:
    """Framework-level action (flush cache, reset circuit breaker, etc.).

    The ``handler`` is a dotted path to an async function accepting
    ``(container, **params)``.
    """

    name: str
    title: str
    contributor: str
    handler: str
    icon: str = "zap"
    confirmation_message: str | None = None
    permission: str | None = None
    destructive: bool = False
    category: str = "operations"
    parameter_schema: ActionParameterSchema | None = None


@dataclass(frozen=True)
class WidgetViewModel:
    """Typed return value for widget rendering.

    Provides a standard contract that all widget renderers follow.
    The ``content`` field carries structured widget content. If ``error`` is set,
    the widget is in an error state and ``content`` should be an error card.
    """

    content: WidgetContent
    title: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class WidgetParams:
    """Typed query parameters passed to a widget handler.

    Pure value object — no parsing, no validation logic, no I/O.
    Parsing belongs in ``quadkit.admin.params.parse_widget_params``.
    """

    page: int = 1
    page_size: int = 20
    time_window_minutes: int = 60
    raw: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    tenant_id: str | None = None


__all__ = [
    "ActionParameterField",
    "ActionParameterSchema",
    "AdminActionDefinition",
    "AdminHealthDefinition",
    "AdminRouteSpec",
    "DashboardWidgetDefinition",
    "ManagementPageDefinition",
    "NavigationContribution",
    "PageCategory",
    "SettingsPanelDefinition",
    "WidgetCategory",
    "WidgetContent",
    "WidgetKind",
    "WidgetParams",
    "WidgetSize",
    "WidgetViewModel",
]
