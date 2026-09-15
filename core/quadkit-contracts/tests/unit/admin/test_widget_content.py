"""Tests for the admin widget content value types."""

from __future__ import annotations

import dataclasses

import pytest

from quadkit.contracts.admin.health_payload import HealthCheckPayload
from quadkit.contracts.admin.widget_content import (
    Stat,
    StatContent,
    TableCell,
    TableContent,
    Tone,
    WidgetContent,
    WidgetKind,
)
from quadkit.contracts.core.health import HealthStatus


def test_stat_content_is_frozen_and_holds_stats() -> None:
    content = StatContent(
        stats=(Stat(label="Uptime", value="3600s", tone=Tone.SUCCESS),)
    )
    assert content.stats[0].tone is Tone.SUCCESS
    with pytest.raises(dataclasses.FrozenInstanceError):
        content.stats = ()


def test_table_content_cells_carry_tone() -> None:
    content = TableContent(
        columns=("Channel", "Status"),
        rows=((TableCell("relay-1"), TableCell("degraded", tone=Tone.WARNING)),),
    )
    assert content.rows[0][1].tone is Tone.WARNING


def test_health_check_payload_is_a_valid_widget_content_member() -> None:
    payload: WidgetContent = HealthCheckPayload(
        status=HealthStatus.HEALTHY, component="web.server"
    )
    assert payload.status is HealthStatus.HEALTHY


def test_widget_kind_values_match_content_variants() -> None:
    assert set(WidgetKind) == {
        WidgetKind.STAT,
        WidgetKind.TABLE,
        WidgetKind.HEALTH,
        WidgetKind.MESSAGE,
        WidgetKind.EMPTY,
        WidgetKind.CHART,
    }
