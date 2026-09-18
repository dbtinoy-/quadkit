"""Tests for the relay rate-limit contracts.

The counter protocol and decision value type are the only surface the
gateway depends on; concrete counters (in-memory, Redis) implement the
protocol behind it.  These tests pin the decision value type and the
protocol surface.
"""
from __future__ import annotations

from quadkit.contracts.ai.relay.ratelimit import (
    RelayRateLimitCounterProtocol,
    RelayRateLimitDecision,
)


def test_decision_and_limit_types() -> None:
    d = RelayRateLimitDecision(allowed=True, count=1, ttl_seconds=300)
    assert d.allowed is True
    assert d.count == 1
    assert d.ttl_seconds == 300
    over = RelayRateLimitDecision(allowed=False, count=31, ttl_seconds=300)
    assert over.allowed is False
    assert over.count == 31


def test_counter_protocol_surface() -> None:
    assert RelayRateLimitCounterProtocol.__name__ == "RelayRateLimitCounterProtocol"
    assert hasattr(RelayRateLimitCounterProtocol, "take")
