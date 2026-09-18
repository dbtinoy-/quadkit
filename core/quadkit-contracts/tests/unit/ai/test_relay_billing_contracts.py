"""Tests for the relay usage, reservation, and billing contracts."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest

from quadkit.contracts.ai.governance import (
    RelayBillingError,
    RelayBillingProtocol,
    RelayChargeBreakdown,
    RelayPriceEstimatorProtocol,
    RelayUsageRecord,
    RelayUsageReservation,
    RelayUsageScope,
    RelayUsageStoreProtocol,
    billing_store_unavailable,
    charge_overflow,
    duplicate_settlement,
    invalid_usage,
    quota_exhausted,
    reservation_expired,
    unknown_price,
)
from quadkit.contracts.ai.relay import RelayConvertResult, RelayUsage
from quadkit.contracts.core.result import Ok, Result

#: How far ahead of the clock a reservation must expire to be accepted. The
#: instant is computed at each use: `RelayUsageReservation` rejects a TTL that
#: is not positive when it is constructed, so anything read once at import
#: expires on a suite that takes longer than the window to reach this module.
TTL = timedelta(minutes=5)

VALID_SCOPE = RelayUsageScope(tenant_id="tenant-1")


def make_reservation(**overrides: Any) -> RelayUsageReservation:
    """Build a valid reservation; override any field."""
    params = {
        "reservation_id": "res-1",
        "request_id": "req-1",
        "estimated_tokens": 100,
        "estimated_charge": Decimal("0.01"),
        "expires_at": datetime.now(UTC) + TTL,
    }
    params.update(overrides)
    return RelayUsageReservation(**params)


def make_record(**overrides: Any) -> RelayUsageRecord:
    """Build a valid settled record; override any field."""
    params = {
        "request_id": "req-1",
        "attempt_id": "att-1",
        "scope": VALID_SCOPE,
        "usage": RelayUsage(prompt_tokens=10, completion_tokens=20),
        "charge": Decimal("0.0015"),
        "currency": "USD",
        "status": "completed",
    }
    params.update(overrides)
    return RelayUsageRecord(**params)


def make_breakdown(**overrides: Any) -> RelayChargeBreakdown:
    """Build a valid breakdown; override any field."""
    params = {
        "prompt": Decimal("0.001"),
        "cached_prompt": Decimal("0.0005"),
        "completion": Decimal("0.002"),
        "reasoning": Decimal("0.0002"),
        "audio_input": Decimal("0.0003"),
        "audio_output": Decimal("0.0004"),
        "image": Decimal("0.0012"),
        "total": Decimal("0.0056"),
    }
    params.update(overrides)
    return RelayChargeBreakdown(**params)


class TestRelayUsageScope:
    def test_defaults(self) -> None:
        scope = VALID_SCOPE
        assert scope.tenant_id == "tenant-1"
        assert scope.account_id is None
        assert scope.user_id is None
        assert scope.model == ""
        assert scope.provider == ""
        assert scope.channel == ""

    def test_rejects_empty_tenant(self) -> None:
        with pytest.raises(ValueError):
            RelayUsageScope(tenant_id="")

    def test_frozen(self) -> None:
        with pytest.raises(FrozenInstanceError):
            VALID_SCOPE.tenant_id = "x"


class TestRelayUsageRecord:
    def test_valid_construction(self) -> None:
        record = make_record()
        assert record.request_id == "req-1"
        assert record.attempt_id == "att-1"
        assert record.scope == VALID_SCOPE
        assert record.charge == Decimal("0.0015")
        assert record.currency == "USD"
        assert record.status == "completed"
        assert record.converter_id is None
        assert record.loss_codes == ()

    def test_rejects_empty_request_id(self) -> None:
        with pytest.raises(ValueError):
            make_record(request_id="")

    def test_rejects_empty_attempt_id(self) -> None:
        with pytest.raises(ValueError):
            make_record(attempt_id="")

    def test_rejects_negative_prompt_tokens(self) -> None:
        with pytest.raises(ValueError):
            make_record(usage=RelayUsage(prompt_tokens=-1))

    def test_rejects_negative_completion_tokens(self) -> None:
        with pytest.raises(ValueError):
            make_record(usage=RelayUsage(completion_tokens=-5))

    def test_rejects_negative_override(self) -> None:
        with pytest.raises(ValueError):
            make_record(usage=RelayUsage(total_tokens_override=-1))

    def test_rejects_negative_charge(self) -> None:
        with pytest.raises(ValueError):
            make_record(charge=Decimal("-0.01"))

    def test_rejects_empty_currency(self) -> None:
        with pytest.raises(ValueError):
            make_record(currency="")

    def test_rejects_unknown_status(self) -> None:
        with pytest.raises(ValueError):
            make_record(status="unknown")

    def test_accepts_all_statuses(self) -> None:
        for status in ("completed", "failed", "cancelled", "truncated"):
            record = make_record(status=status)  # type: ignore[arg-type]
            assert record.status == status

    def test_frozen(self) -> None:
        with pytest.raises(FrozenInstanceError):
            make_record().request_id = "x"


class TestRelayUsageReservation:
    def test_valid_construction(self) -> None:
        expires_at = datetime.now(UTC) + TTL
        reservation = make_reservation(expires_at=expires_at)
        assert reservation.reservation_id == "res-1"
        assert reservation.request_id == "req-1"
        assert reservation.estimated_tokens == 100
        assert reservation.estimated_charge == Decimal("0.01")
        assert reservation.expires_at == expires_at

    def test_rejects_empty_reservation_id(self) -> None:
        with pytest.raises(ValueError):
            make_reservation(reservation_id="")

    def test_rejects_empty_request_id(self) -> None:
        with pytest.raises(ValueError):
            make_reservation(request_id="")

    def test_rejects_negative_estimated_tokens(self) -> None:
        with pytest.raises(ValueError):
            make_reservation(estimated_tokens=-1)

    def test_rejects_negative_estimated_charge(self) -> None:
        with pytest.raises(ValueError):
            make_reservation(estimated_charge=Decimal("-0.01"))

    def test_rejects_non_positive_ttl(self) -> None:
        with pytest.raises(ValueError):
            make_reservation(expires_at=datetime.now(UTC) - TTL)
        with pytest.raises(ValueError):
            make_reservation(expires_at=datetime.now(UTC))

    def test_frozen(self) -> None:
        with pytest.raises(FrozenInstanceError):
            make_reservation().reservation_id = "x"


class TestRelayChargeBreakdown:
    def test_valid_construction(self) -> None:
        breakdown = make_breakdown()
        assert breakdown.total == Decimal("0.0056")

    def test_accepts_explicit_zero_dimension(self) -> None:
        breakdown = make_breakdown(audio_input=Decimal("0"))
        assert breakdown.audio_input == Decimal("0")

    def test_rejects_negative_price(self) -> None:
        with pytest.raises(ValueError):
            make_breakdown(prompt=Decimal("-0.001"))
        with pytest.raises(ValueError):
            make_breakdown(total=Decimal("-0.001"))

    def test_frozen(self) -> None:
        with pytest.raises(FrozenInstanceError):
            make_breakdown().total = Decimal("0")


class TestRelayBillingErrorFactories:
    def test_codes(self) -> None:
        factories = {
            unknown_price(): "unknown_price",
            quota_exhausted(): "quota_exhausted",
            reservation_expired(): "reservation_expired",
            duplicate_settlement(): "duplicate_settlement",
            invalid_usage(): "invalid_usage",
            billing_store_unavailable(): "billing_store_unavailable",
            charge_overflow(): "charge_overflow",
        }
        for error, code in factories.items():
            assert isinstance(error, RelayBillingError)
            assert error.code == code
            assert error.message

    def test_carries_request_and_tenant_ids(self) -> None:
        error = quota_exhausted(request_id="req-1", tenant_id="tenant-1")
        assert error.request_id == "req-1"
        assert error.tenant_id == "tenant-1"

    def test_no_payload_field(self) -> None:
        error = invalid_usage()
        assert not hasattr(error, "payload")


class _StubStore:
    """Minimal ``RelayUsageStoreProtocol`` double."""

    async def save_reservation(self, reservation: RelayUsageReservation) -> None:
        """No-op."""

    async def settle_once(self, record: RelayUsageRecord) -> RelayUsageRecord:
        """Return the record unchanged."""
        return record

    async def release(self, reservation_id: str) -> None:
        """No-op."""

    async def query(self, filters: Any) -> list[RelayUsageRecord]:
        """Return nothing."""
        return []


class _StubEstimator:
    """Minimal ``RelayPriceEstimatorProtocol`` double."""

    def estimate_charge(
        self,
        model: str,
        usage: RelayUsage,
        *,
        provider: str = "",
        channel: str = "",
    ) -> Result[RelayChargeBreakdown, RelayBillingError]:
        """Return a zero breakdown."""
        zero = Decimal("0")
        return Ok(
            RelayChargeBreakdown(
                prompt=zero,
                cached_prompt=zero,
                completion=zero,
                reasoning=zero,
                audio_input=zero,
                audio_output=zero,
                image=zero,
                total=zero,
            )
        )


class _StubBilling:
    """Minimal ``RelayBillingProtocol`` double."""

    async def pre_consume(
        self, request_id: str, scope: RelayUsageScope, payload: Any
    ) -> Any:
        """Unused by shape tests."""
        raise NotImplementedError

    async def settle(
        self, reservation: RelayUsageReservation, result: RelayConvertResult, *, status: str
    ) -> Any:
        """Unused by shape tests."""
        raise NotImplementedError

    async def release(self, reservation: RelayUsageReservation) -> None:
        """Unused by shape tests."""


class _StubBillingMissingSettle:
    """Billing double missing the ``settle`` member."""

    async def pre_consume(
        self, request_id: str, scope: RelayUsageScope, payload: Any
    ) -> Any:
        """Unused by shape tests."""
        raise NotImplementedError

    async def release(self, reservation: RelayUsageReservation) -> None:
        """Unused by shape tests."""


class TestProtocolShapes:
    def test_store_protocol_runtime_checkable(self) -> None:
        assert isinstance(_StubStore(), RelayUsageStoreProtocol)

    def test_estimator_protocol_runtime_checkable(self) -> None:
        assert isinstance(_StubEstimator(), RelayPriceEstimatorProtocol)

    def test_billing_protocol_runtime_checkable(self) -> None:
        assert isinstance(_StubBilling(), RelayBillingProtocol)
        assert not isinstance(_StubBillingMissingSettle(), RelayBillingProtocol)

    def test_billing_protocol_missing_member_rejected(self) -> None:
        class MissingRelease:
            """Missing the ``release`` member."""

            async def pre_consume(
                self, request_id: str, scope: RelayUsageScope, payload: Any
            ) -> Any:
                """Unused by shape tests."""
                raise NotImplementedError

            async def settle(
                self,
                reservation: RelayUsageReservation,
                result: RelayConvertResult,
                *,
                status: str,
            ) -> Any:
                """Unused by shape tests."""
                raise NotImplementedError

        assert not isinstance(MissingRelease(), RelayBillingProtocol)


class TestRelayUsageDimensions:
    def test_preserves_all_dimensions(self) -> None:
        usage = RelayUsage(
            prompt_tokens=10,
            completion_tokens=20,
            cache_read_tokens=5,
            cache_creation_tokens=3,
            reasoning_tokens=2,
            audio_input_tokens=1,
            audio_output_tokens=1,
            image_tokens=4,
            input_tokens=10,
            output_tokens=20,
        )
        assert usage.prompt_tokens == 10
        assert usage.completion_tokens == 20
        assert usage.cache_read_tokens == 5
        assert usage.cache_creation_tokens == 3
        assert usage.reasoning_tokens == 2
        assert usage.audio_input_tokens == 1
        assert usage.audio_output_tokens == 1
        assert usage.image_tokens == 4
        assert usage.input_tokens == 10
        assert usage.output_tokens == 20

    def test_total_is_sum_without_override(self) -> None:
        usage = RelayUsage(prompt_tokens=10, completion_tokens=20)
        assert usage.total_tokens == 30

    def test_explicit_zero_distinct_from_missing(self) -> None:
        zero = RelayUsage()
        assert zero.total_tokens == 0
        assert zero.total_tokens_override is None
        assert zero.prompt_tokens == 0
        explicit = RelayUsage(prompt_tokens=0, completion_tokens=0)
        assert explicit.total_tokens == 0
        assert explicit.total_tokens_override is None

    def test_override_wins(self) -> None:
        usage = RelayUsage(prompt_tokens=10, completion_tokens=20, total_tokens_override=25)
        assert usage.total_tokens == 25

    def test_to_token_usage_mapping(self) -> None:
        usage = RelayUsage(prompt_tokens=10, completion_tokens=20)
        token_usage = usage.to_token_usage()
        assert token_usage.prompt_tokens == 10
        assert token_usage.completion_tokens == 20
        assert token_usage.total_tokens == 30
