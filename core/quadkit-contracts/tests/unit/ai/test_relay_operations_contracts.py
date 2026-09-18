"""Contract tests for relay operational value types and protocols.

Covers ``quadkit.contracts.ai.relay.operations``: the immutable
health/metrics/report value types, policy snapshots and changes, and
the read/control service protocols.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

import pytest

from quadkit.contracts.ai.relay import (
    RelayActiveStream,
    RelayChannelHealth,
    RelayFormat,
    RelayOperationsControlProtocol,
    RelayOperationsProtocol,
    RelayPolicyChange,
    RelayPolicySnapshot,
    RelayPolicyStoreProtocol,
    RelayRegistryDiagnostics,
    RelayRouteMetrics,
    TimeWindow,
)
from quadkit.contracts.ai.relay.types import ConversionQuality

T0 = datetime(2026, 8, 1, 10, 0, tzinfo=UTC)
T1 = datetime(2026, 8, 1, 11, 0, tzinfo=UTC)


class TestTimeWindow:
    """TimeWindow bounds validation."""

    def test_accepts_forward_window(self) -> None:
        window = TimeWindow(start=T0, end=T1)
        assert window.start == T0
        assert window.end == T1

    def test_rejects_inverted_window(self) -> None:
        with pytest.raises(ValueError, match="end must be after"):
            TimeWindow(start=T1, end=T0)

    def test_rejects_zero_length_window(self) -> None:
        with pytest.raises(ValueError, match="end must be after"):
            TimeWindow(start=T0, end=T0)


class TestRelayChannelHealth:
    def test_valid_snapshot(self) -> None:
        health = RelayChannelHealth(
            channel="claude",
            target=RelayFormat.CLAUDE,
            status="healthy",
            model_count=3,
            latency_ms_p50=210.0,
            latency_ms_p95=540.0,
            failure_count=0,
            checked_at=T1,
        )
        assert health.channel == "claude"
        assert health.status == "healthy"
        assert health.model_count == 3

    def test_rejects_unknown_status(self) -> None:
        with pytest.raises(ValueError, match="unknown channel health status"):
            RelayChannelHealth(
                channel="claude",
                target=RelayFormat.CLAUDE,
                status="exploded",  # type: ignore[arg-type]
                model_count=1,
                latency_ms_p50=None,
                latency_ms_p95=None,
                failure_count=0,
                checked_at=T1,
            )

    def test_rejects_negative_model_count(self) -> None:
        with pytest.raises(ValueError, match="model_count must not be negative"):
            RelayChannelHealth(
                channel="claude",
                target=RelayFormat.CLAUDE,
                status="healthy",
                model_count=-1,
                latency_ms_p50=None,
                latency_ms_p95=None,
                failure_count=0,
                checked_at=T1,
            )

    def test_rejects_negative_latency(self) -> None:
        with pytest.raises(ValueError, match="latency_ms_p50 must not be negative"):
            RelayChannelHealth(
                channel="claude",
                target=RelayFormat.CLAUDE,
                status="healthy",
                model_count=1,
                latency_ms_p50=-5.0,
                latency_ms_p95=None,
                failure_count=0,
                checked_at=T1,
            )

    def test_rejects_negative_failure_count(self) -> None:
        with pytest.raises(ValueError, match="failure_count must not be negative"):
            RelayChannelHealth(
                channel="claude",
                target=RelayFormat.CLAUDE,
                status="healthy",
                model_count=1,
                latency_ms_p50=None,
                latency_ms_p95=None,
                failure_count=-1,
                checked_at=T1,
            )

    def test_rejects_empty_channel(self) -> None:
        with pytest.raises(ValueError, match="channel must not be empty"):
            RelayChannelHealth(
                channel="",
                target=RelayFormat.CLAUDE,
                status="healthy",
                model_count=1,
                latency_ms_p50=None,
                latency_ms_p95=None,
                failure_count=0,
                checked_at=T1,
            )

    def test_accepts_unknown_latencies_for_unavailable(self) -> None:
        health = RelayChannelHealth(
            channel="gemini",
            target=RelayFormat.GEMINI,
            status="unavailable",
            model_count=0,
            latency_ms_p50=None,
            latency_ms_p95=None,
            failure_count=0,
            checked_at=T1,
        )
        assert health.latency_ms_p50 is None


class TestRelayRouteMetrics:
    def test_valid_metrics(self) -> None:
        metrics = RelayRouteMetrics(
            source=RelayFormat.OPENAI_CHAT,
            target=RelayFormat.CLAUDE,
            quality=ConversionQuality.GOOD,
            request_count=42,
            loss_counts={"unsupported_option": 2},
            unsupported_count=1,
            stream_failure_count=0,
            converter_id="builtin",
            window_start=T0,
            window_end=T1,
        )
        assert metrics.request_count == 42
        assert metrics.loss_counts == {"unsupported_option": 2}
        assert metrics.converter_id == "builtin"

    def test_rejects_negative_request_count(self) -> None:
        with pytest.raises(ValueError, match="request_count must not be negative"):
            RelayRouteMetrics(
                source=RelayFormat.OPENAI_CHAT,
                target=RelayFormat.CLAUDE,
                quality=ConversionQuality.GOOD,
                request_count=-1,
                loss_counts={},
                unsupported_count=0,
                stream_failure_count=0,
                converter_id=None,
                window_start=T0,
                window_end=T1,
            )

    def test_rejects_inverted_window(self) -> None:
        with pytest.raises(ValueError, match="window end must be after"):
            RelayRouteMetrics(
                source=RelayFormat.OPENAI_CHAT,
                target=RelayFormat.CLAUDE,
                quality=ConversionQuality.GOOD,
                request_count=1,
                loss_counts={},
                unsupported_count=0,
                stream_failure_count=0,
                converter_id=None,
                window_start=T1,
                window_end=T0,
            )


class TestRelayRegistryDiagnostics:
    def test_valid_diagnostics(self) -> None:
        diagnostics = RelayRegistryDiagnostics(
            converter_id="relay-converter",
            converter_version="1.0.0",
            mapper_ids=("claude", "gemini", "openai_chat", "openai_responses"),
            supported_routes=(
                (RelayFormat.OPENAI_CHAT, RelayFormat.CLAUDE),
                (RelayFormat.GEMINI, RelayFormat.OPENAI_CHAT),
            ),
        )
        assert diagnostics.converter_id == "relay-converter"
        assert len(diagnostics.supported_routes) == 2

    def test_default_registration_errors(self) -> None:
        diagnostics = RelayRegistryDiagnostics(
            converter_id="relay-converter",
            converter_version="1.0.0",
            mapper_ids=(),
            supported_routes=(),
        )
        assert diagnostics.registration_errors == ()


class TestRelayPolicySnapshot:
    def test_valid_snapshot(self) -> None:
        snapshot = RelayPolicySnapshot(
            enabled_channels={"claude": True, "gemini": False},
            allowed_model_options={"claude": frozenset({"haiku"})},
            media_allowed_schemes=frozenset({"https"}),
            media_allowed_hosts=frozenset({"r.jina.ai"}),
            max_request_bytes=10_000_000,
            max_stream_seconds=300.0,
        )
        assert snapshot.enabled_channels["claude"] is True
        assert snapshot.max_request_bytes == 10_000_000

    def test_rejects_wildcard_host(self) -> None:
        with pytest.raises(
            ValueError, match="media_allowed_hosts must not contain wildcards"
        ):
            RelayPolicySnapshot(
                enabled_channels={},
                allowed_model_options={},
                media_allowed_schemes=frozenset({"https"}),
                media_allowed_hosts=frozenset({"*"}),
                max_request_bytes=1,
                max_stream_seconds=1.0,
            )

    def test_rejects_negative_max_request_bytes(self) -> None:
        with pytest.raises(ValueError, match="max_request_bytes must not be negative"):
            RelayPolicySnapshot(
                enabled_channels={},
                allowed_model_options={},
                media_allowed_schemes=frozenset(),
                media_allowed_hosts=frozenset(),
                max_request_bytes=-1,
                max_stream_seconds=1.0,
            )

    def test_rejects_non_positive_max_stream_seconds(self) -> None:
        with pytest.raises(ValueError, match="max_stream_seconds must be positive"):
            RelayPolicySnapshot(
                enabled_channels={},
                allowed_model_options={},
                media_allowed_schemes=frozenset(),
                media_allowed_hosts=frozenset(),
                max_request_bytes=1,
                max_stream_seconds=0.0,
            )


class TestRelayPolicyChange:
    def test_empty_change_is_noop(self) -> None:
        change = RelayPolicyChange()
        assert change.channel is None
        assert change.enabled is None
        assert change.max_request_bytes is None

    def test_partial_mutation_only(self) -> None:
        change = RelayPolicyChange(channel="claude", enabled=False)
        assert change.channel == "claude"
        assert change.enabled is False
        assert change.allowed_model_options is None
        assert change.media_allowed_schemes is None
        assert change.max_stream_seconds is None

    def test_rejects_wildcard_host(self) -> None:
        with pytest.raises(
            ValueError, match="media_allowed_hosts must not contain wildcards"
        ):
            RelayPolicyChange(media_allowed_hosts=frozenset({"*"}))

    def test_rejects_negative_max_request_bytes(self) -> None:
        with pytest.raises(ValueError, match="max_request_bytes must not be negative"):
            RelayPolicyChange(max_request_bytes=-1)

    def test_rejects_non_positive_max_stream_seconds(self) -> None:
        with pytest.raises(ValueError, match="max_stream_seconds must be positive"):
            RelayPolicyChange(max_stream_seconds=0.0)


class FakeOperations(RelayOperationsProtocol):
    async def channel_health(self) -> Sequence[RelayChannelHealth]:
        return []

    async def route_metrics(
        self,
        window: TimeWindow,
    ) -> Sequence[RelayRouteMetrics]:
        return []

    async def registry_diagnostics(self) -> RelayRegistryDiagnostics:
        return RelayRegistryDiagnostics(
            converter_id="fake",
            converter_version="1.0.0",
            mapper_ids=(),
            supported_routes=(),
        )

    async def policy_snapshot(self) -> RelayPolicySnapshot:
        return RelayPolicySnapshot(
            enabled_channels={},
            allowed_model_options={},
            media_allowed_schemes=frozenset(),
            media_allowed_hosts=frozenset(),
            max_request_bytes=1,
            max_stream_seconds=1.0,
        )

    async def active_streams(self) -> Sequence[RelayActiveStream]:
        return []


class FakeControl:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def set_channel_state(
        self, channel: str, enabled: bool, actor_id: str
    ) -> None:
        self.calls.append(f"set:{channel}:{enabled}:{actor_id}")

    async def update_policy(self, change: RelayPolicyChange, actor_id: str) -> None:
        self.calls.append(f"policy:{actor_id}")

    async def policy_snapshot(self, actor_id: str) -> RelayPolicySnapshot:
        self.calls.append(f"snapshot:{actor_id}")
        return RelayPolicySnapshot(
            enabled_channels={},
            allowed_model_options={},
            media_allowed_schemes=frozenset(),
            media_allowed_hosts=frozenset(),
            max_request_bytes=1,
            max_stream_seconds=1.0,
        )

    async def force_cancel_stream(
        self, stream_id: str, actor_id: str
    ) -> None:
        self.calls.append(f"cancel:{stream_id}:{actor_id}")


class FakePolicyStore(RelayPolicyStoreProtocol):
    def __init__(self) -> None:
        self.current = RelayPolicySnapshot(
            enabled_channels={},
            allowed_model_options={},
            media_allowed_schemes=frozenset(),
            media_allowed_hosts=frozenset(),
            max_request_bytes=1,
            max_stream_seconds=1.0,
        )

    async def load(self) -> RelayPolicySnapshot:
        return self.current

    async def save(self, snapshot: RelayPolicySnapshot) -> None:
        self.current = snapshot


class TestRelayPolicyStoreProtocol:
    def test_protocol_is_runtime_checkable(self) -> None:
        assert isinstance(FakePolicyStore(), RelayPolicyStoreProtocol)

    def test_protocol_method_names(self) -> None:
        for name in ("load", "save"):
            assert hasattr(RelayPolicyStoreProtocol, name)

    @pytest.mark.asyncio
    async def test_store_round_trips_snapshot(self) -> None:
        store = FakePolicyStore()
        initial = await store.load()
        assert initial.max_request_bytes == 1
        replacement = RelayPolicySnapshot(
            enabled_channels={"claude": False},
            allowed_model_options={"claude": frozenset({"model-a"})},
            media_allowed_schemes=frozenset({"https"}),
            media_allowed_hosts=frozenset({"cdn.example.com"}),
            max_request_bytes=4096,
            max_stream_seconds=120.0,
        )
        await store.save(replacement)
        assert await store.load() == replacement


class TestRelayOperationsProtocolShape:
    def test_protocol_is_runtime_checkable(self) -> None:
        assert isinstance(FakeOperations(), RelayOperationsProtocol)

    def test_protocol_method_names(self) -> None:
        for name in (
            "channel_health",
            "route_metrics",
            "registry_diagnostics",
            "policy_snapshot",
            "active_streams",
        ):
            assert hasattr(RelayOperationsProtocol, name)

    @pytest.mark.asyncio
    async def test_shape_matches_expected_signature(self) -> None:
        ops = FakeOperations()
        health = await ops.channel_health()
        assert health == []
        diagnostics = await ops.registry_diagnostics()
        assert diagnostics.converter_version == "1.0.0"
        assert await ops.active_streams() == []


class TestRelayOperationsControlProtocol:
    def test_protocol_is_runtime_checkable(self) -> None:
        assert isinstance(FakeControl(), RelayOperationsControlProtocol)

    def test_protocol_method_names(self) -> None:
        for name in (
            "set_channel_state",
            "update_policy",
            "policy_snapshot",
            "force_cancel_stream",
        ):
            assert hasattr(RelayOperationsControlProtocol, name)

    @pytest.mark.asyncio
    async def test_control_shape(self) -> None:
        control = FakeControl()
        await control.set_channel_state("claude", False, "admin-1")
        await control.update_policy(RelayPolicyChange(enabled=True), "admin-2")
        await control.policy_snapshot("admin-3")
        await control.force_cancel_stream("stream-1", "admin-4")
        assert control.calls == [
            "set:claude:False:admin-1",
            "policy:admin-2",
            "snapshot:admin-3",
            "cancel:stream-1:admin-4",
        ]
