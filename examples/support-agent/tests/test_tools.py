"""Tests for the support desk tools."""

from __future__ import annotations

import pytest

from support_agent.repository.fixtures import KB
from support_agent.tools import (
    SUPPORT_TOOLS,
    calculate_refund,
    lookup_order,
    search_kb,
)


class TestLookupOrder:
    @pytest.mark.asyncio
    async def test_known_order_returns_details(self) -> None:
        result = await lookup_order(order_id="A-100")

        assert result["found"] is True
        assert result["status"] == "shipped"
        assert result["tracking"] == "FS123456789"

    @pytest.mark.asyncio
    async def test_unknown_order_reports_missing(self) -> None:
        assert (await lookup_order(order_id="NOPE"))["found"] is False


class TestCalculateRefund:
    @pytest.mark.asyncio
    async def test_within_seven_days_full_refund(self) -> None:
        result = await calculate_refund(order_total=100.0, days_since_delivery=5)
        assert (result["tier"], result["amount"]) == ("full", 100.0)

    @pytest.mark.asyncio
    async def test_within_thirty_days_half_refund(self) -> None:
        result = await calculate_refund(order_total=100.0, days_since_delivery=20)
        assert (result["tier"], result["amount"]) == ("half", 50.0)

    @pytest.mark.asyncio
    async def test_beyond_thirty_days_no_refund(self) -> None:
        result = await calculate_refund(order_total=100.0, days_since_delivery=45)
        assert (result["tier"], result["amount"]) == ("none", 0.0)

    @pytest.mark.asyncio
    async def test_tier_boundaries(self) -> None:
        tiers = [
            (await calculate_refund(100.0, d))["tier"] for d in (7, 8, 30, 31)
        ]
        assert tiers == ["full", "half", "half", "none"]


class TestSearchKb:
    @pytest.mark.asyncio
    async def test_keyword_match_returns_snippets(self) -> None:
        results = await search_kb(query="refund shipping")
        assert results
        assert all(set(r) == {"title", "snippet"} for r in results)

    @pytest.mark.asyncio
    async def test_no_match_returns_empty(self) -> None:
        assert await search_kb(query="zzzunmatchable") == []


def test_tool_surface() -> None:
    assert set(SUPPORT_TOOLS.keys()) == {
        "lookup_order",
        "calculate_refund",
        "search_kb",
    }
    assert {t.name for t in SUPPORT_TOOLS.values()} == set(SUPPORT_TOOLS.keys())
    assert len(KB) >= 6
