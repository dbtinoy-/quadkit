"""Tests for ProjectionTier enum and SLO tier extension."""
from __future__ import annotations

from datetime import timedelta

import pytest

from quadkit.contracts.monitor.projection_tier import ProjectionTier
from quadkit.monitor.slo.objective import SLO


class TestProjectionTier:
    def test_is_str_enum(self):
        assert issubclass(ProjectionTier, str)
        assert hasattr(ProjectionTier, "P0_PAGE")

    def test_has_three_tiers(self):
        values = list(ProjectionTier)
        assert len(values) == 3

    def test_values(self):
        assert ProjectionTier.P0_PAGE.value == "p0_page"
        assert ProjectionTier.P1_BUSINESS_HOURS.value == "p1_business_hours"
        assert ProjectionTier.P2_DIGEST.value == "p2_digest"


class TestSLOWithTier:
    def test_default_tier_is_p1(self):
        slo = SLO(name="test", metric="m", percentile=0.99, threshold_ms=100.0)
        assert slo.tier == ProjectionTier.P1_BUSINESS_HOURS

    def test_custom_tier(self):
        slo = SLO(
            name="test",
            metric="m",
            percentile=0.99,
            threshold_ms=100.0,
            tier=ProjectionTier.P0_PAGE,
        )
        assert slo.tier == ProjectionTier.P0_PAGE

    def test_default_owner_is_empty(self):
        slo = SLO(name="test", metric="m", percentile=0.99, threshold_ms=100.0)
        assert slo.owner == ""

    def test_custom_owner(self):
        slo = SLO(
            name="test",
            metric="m",
            percentile=0.99,
            threshold_ms=100.0,
            owner="TPS-001",
        )
        assert slo.owner == "TPS-001"

    def test_default_runbook_url_is_none(self):
        slo = SLO(name="test", metric="m", percentile=0.99, threshold_ms=100.0)
        assert slo.runbook_url is None

    def test_custom_runbook_url(self):
        slo = SLO(
            name="test",
            metric="m",
            percentile=0.99,
            threshold_ms=100.0,
            runbook_url="https://ops.runbook/test",
        )
        assert slo.runbook_url == "https://ops.runbook/test"

    def test_backwards_compatible_construction(self):
        """SLO created without new fields still works."""
        slo = SLO(name="legacy", metric="m", percentile=0.99, threshold_ms=200.0)
        assert slo.window == timedelta(hours=1)
        assert slo.tier == ProjectionTier.P1_BUSINESS_HOURS
        assert slo.owner == ""
        assert slo.runbook_url is None
