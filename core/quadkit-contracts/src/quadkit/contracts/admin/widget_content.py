"""Structured widget content value types for the admin contributor system.

Host-side rendering turns these into HTML — contributors return
``WidgetContent`` from ``render_widget`` instead of hand-building markup.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

from quadkit.contracts.admin.health_payload import HealthCheckPayload


class Tone(StrEnum):
    """Visual tone/severity for widget content elements."""

    DEFAULT = "default"
    PRIMARY = "primary"
    SUCCESS = "success"
    WARNING = "warning"
    DANGER = "danger"
    INFO = "info"


class WidgetKind(StrEnum):
    """Kind of dashboard widget, declared by the widget definition."""

    STAT = "stat"
    TABLE = "table"
    HEALTH = "health"
    MESSAGE = "message"
    EMPTY = "empty"
    CHART = "chart"


@dataclass(frozen=True)
class Stat:
    """A single labeled stat value."""

    label: str
    value: str
    delta: str | None = None
    tone: Tone = Tone.DEFAULT
    icon: str | None = None
    sparkline_data: tuple[float, ...] = ()


@dataclass(frozen=True)
class StatContent:
    """One stat or an N-stat grid."""

    stats: tuple[Stat, ...]


@dataclass(frozen=True)
class TableCell:
    """A single table cell."""

    text: str
    tone: Tone = Tone.DEFAULT


@dataclass(frozen=True)
class TableContent:
    """A table of rows."""

    columns: tuple[str, ...]
    rows: tuple[tuple[TableCell, ...], ...]
    empty_message: str = "No data available."


@dataclass(frozen=True)
class MessageContent:
    """A plain status message."""

    text: str
    tone: Tone = Tone.DEFAULT


@dataclass(frozen=True)
class EmptyContent:
    """An empty / no-data state."""

    title: str = "No data available"
    message: str = "There's nothing to display yet."
    icon: str = "inbox"


@dataclass(frozen=True)
class ChartPoint:
    """A single named bar-chart point."""

    label: str
    value: float
    tone: Tone = Tone.DEFAULT
    secondary_value: float | None = None


@dataclass(frozen=True)
class ChartContent:
    """A small chart of named points."""

    points: tuple[ChartPoint, ...]
    chart_type: Literal["bar", "line", "pie", "area"] = "bar"


WidgetContent = (
    StatContent
    | TableContent
    | HealthCheckPayload  # from quadkit.contracts.admin.health_payload — reused, not duplicated
    | MessageContent
    | EmptyContent
    | ChartContent
)

__all__ = [
    "ChartContent",
    "ChartPoint",
    "EmptyContent",
    "MessageContent",
    "Stat",
    "StatContent",
    "TableCell",
    "TableContent",
    "Tone",
    "WidgetContent",
    "WidgetKind",
]
