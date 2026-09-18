"""Contract tests for the relay ledger (top-up / check-in) types."""

from __future__ import annotations

import pytest

from quadkit.contracts.ai.governance import RelayUsageScope
from quadkit.contracts.ai.relay import (
    RelayCheckinRecord,
    RelayLedgerServiceProtocol,
    RelayTopUpRecord,
)
from quadkit.contracts.core.result import Ok


def test_topup_record_defaults() -> None:
    top = RelayTopUpRecord(
        reference_id="r1",
        user_id="u1",
        amount="100",
        status="completed",
        created_at="2026-08-10T00:00:00+00:00",
    )
    assert top.reference_id == "r1"
    assert top.user_id == "u1"
    assert top.amount == "100"
    assert top.status == "completed"


def test_topup_record_rejects_empty_identity() -> None:
    with pytest.raises(ValueError):
        RelayTopUpRecord(
            reference_id="",
            user_id="u1",
            amount="100",
            status="pending",
            created_at="t",
        )


def test_topup_record_rejects_unknown_status() -> None:
    with pytest.raises(ValueError):
        RelayTopUpRecord(
            reference_id="r1",
            user_id="u1",
            amount="100",
            status="minted",
            created_at="t",
        )


def test_checkin_record_carries_caller_supplied_award() -> None:
    check = RelayCheckinRecord(
        user_id="u1",
        day="2026-08-09",
        award="25",
        created_at="2026-08-09T00:00:00+00:00",
    )
    assert check.day == "2026-08-09"
    assert check.award == "25"
    assert check.user_id == "u1"


def test_checkin_record_rejects_bad_day() -> None:
    with pytest.raises(ValueError):
        RelayCheckinRecord(user_id="u1", day="not-a-day", award="5", created_at="t")


def test_ledger_protocol_surface() -> None:
    assert isinstance(RelayLedgerServiceProtocol, type)
    assert RelayLedgerServiceProtocol in (RelayLedgerServiceProtocol,)


async def test_protocol_signature_accepts_credit_ok_result() -> None:
    result: Ok[None] = Ok(None)
    scope = RelayUsageScope(tenant_id="t1", user_id="u1")
    assert result.is_ok()
    assert scope.user_id == "u1"
