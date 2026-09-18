"""Tests for the relay request-log and usage read contracts.

The entry value type and the write/read protocols are the only surface
the gateway and governance depend on: the gateway emits entries, the
store persists them, and the usage service serves aggregates.  These
tests pin the required metadata fields and the protocol surfaces.
"""

from __future__ import annotations

from datetime import datetime

from quadkit.contracts.ai.relay.logs import (
    RelayRequestLogEntry,
    RelayRequestLogStoreProtocol,
)
from quadkit.contracts.ai.relay.usage import (
    RelayDailyUsage,
    RelayModelRank,
    RelayUsageServiceProtocol,
)


def test_entry_has_required_metadata_fields() -> None:
    entry = RelayRequestLogEntry(
        request_id="req-1",
        user_id="u1",
        token_id="t1",
        endpoint_kind="chat",
        model="gpt-4",
        channel_name="ch-1",
        status="completed",
        created_at=datetime(2026, 8, 10, 12, 0, 0),
    )
    assert entry.request_id == "req-1"
    assert entry.user_id == "u1"
    assert entry.token_id == "t1"
    assert entry.endpoint_kind == "chat"
    assert entry.model == "gpt-4"
    assert entry.channel_name == "ch-1"
    assert entry.status == "completed"
    assert entry.prompt_tokens == 0
    assert entry.completion_tokens == 0
    assert entry.cost == "0"
    assert entry.latency_ms == 0
    assert entry.error_code == ""


def test_log_store_protocol_is_runtime_checkable() -> None:
    assert RelayRequestLogStoreProtocol.__name__ == "RelayRequestLogStoreProtocol"
    assert hasattr(RelayRequestLogStoreProtocol, "append")


def test_usage_value_types() -> None:
    daily = RelayDailyUsage(
        day="2026-08-10", prompt_tokens=10, completion_tokens=20, cost="0.05"
    )
    assert daily.prompt_tokens == 10
    assert daily.completion_tokens == 20
    rank = RelayModelRank(
        model="gpt-4", completion_tokens=200, request_count=4, cost="0.5"
    )
    assert rank.model == "gpt-4"
    assert rank.request_count == 4


def test_usage_service_protocol_is_runtime_checkable() -> None:
    assert RelayUsageServiceProtocol.__name__ == "RelayUsageServiceProtocol"
    assert hasattr(RelayUsageServiceProtocol, "daily_usage")
    assert hasattr(RelayUsageServiceProtocol, "model_rank")
    assert hasattr(RelayUsageServiceProtocol, "list_requests")
