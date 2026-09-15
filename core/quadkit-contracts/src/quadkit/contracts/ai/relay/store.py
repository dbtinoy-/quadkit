"""Durable relay channel store contracts.

Statically configured channels remain the default; a host may bind a
durable store at boot and the gateway reconciles its registry from it.
All mutations compare-and-set on ``revision`` so stale writers are
rejected instead of overwriting newer state.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from quadkit.contracts.ai.relay.gateway import RelayChannel


@dataclass(frozen=True, slots=True)
class RelayChannelSnapshot:
    """One durable channel row with its revision."""

    channel: RelayChannel
    revision: int
    created_at: str
    updated_at: str


@runtime_checkable
class RelayChannelStoreProtocol(Protocol):
    """CRUD over durable relay channel rows.

    ``upsert`` matches on ``channel.name``; it returns the new revision
    on success and ``None`` when ``expected_revision`` does not match
    (stale write).  ``delete`` returns ``False`` when the channel does
    not exist.
    """

    async def list_channels(self) -> list[RelayChannelSnapshot]: ...

    async def upsert(
        self, channel: RelayChannel, *, expected_revision: int | None = None
    ) -> int | None: ...

    async def delete(self, name: str, *, expected_revision: int) -> bool: ...


__all__ = ["RelayChannelSnapshot", "RelayChannelStoreProtocol"]
