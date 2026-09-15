"""Tests for the durable relay channel store contracts."""

from __future__ import annotations

from quadkit.contracts.ai.relay.gateway import RelayChannel
from quadkit.contracts.ai.relay.store import (
    RelayChannelSnapshot,
    RelayChannelStoreProtocol,
)
from quadkit.contracts.ai.relay.types import RelayFormat


def test_snapshot_round_trips_channel_fields() -> None:
    channel = RelayChannel(
        name="c1",
        upstream_base_url="https://u",
        target_format=RelayFormat.OPENAI_CHAT,
        models=("m1", "m2"),
        priority=50,
        enabled=True,
    )
    snapshot = RelayChannelSnapshot(
        channel=channel, revision=3, created_at="t1", updated_at="t2"
    )
    assert snapshot.channel.name == "c1"
    assert snapshot.channel.upstream_base_url == "https://u"
    assert snapshot.channel.target_format == RelayFormat.OPENAI_CHAT
    assert snapshot.channel.models == ("m1", "m2")
    assert snapshot.channel.priority == 50
    assert snapshot.revision == 3
    assert snapshot.created_at == "t1"
    assert snapshot.updated_at == "t2"


def test_store_protocol_is_runtime_checkable() -> None:
    assert RelayChannelStoreProtocol.__name__ == "RelayChannelStoreProtocol"
    assert hasattr(RelayChannelStoreProtocol, "list_channels")
    assert hasattr(RelayChannelStoreProtocol, "upsert")
    assert hasattr(RelayChannelStoreProtocol, "delete")