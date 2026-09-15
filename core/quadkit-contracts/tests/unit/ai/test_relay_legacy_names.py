"""Negative tests for obsolete relay draft API names.

The historical names ``RelayProtocol``, ``RelayConfig``, ``PassthroughData``,
and ``StreamMode`` are draft artifacts and must not be reintroduced into the
live relay package.  The unrelated event-outbox ``OutboxRelayProtocol`` is
explicitly out of scope and untouched.
"""
from __future__ import annotations

import pytest

OBSOLETE_NAMES = ("RelayProtocol", "RelayConfig", "PassthroughData", "StreamMode")


@pytest.mark.parametrize("name", OBSOLETE_NAMES)
def test_obsolete_relay_name_not_exported(name: str) -> None:
    """Obsolete draft names are absent from the relay package root."""
    import quadkit.contracts.ai.relay as relay

    assert not hasattr(relay, name), f"obsolete draft name {name!r} is exported"


@pytest.mark.parametrize("name", OBSOLETE_NAMES)
def test_obsolete_relay_name_not_importable(name: str) -> None:
    """Obsolete draft names raise ImportError from the relay package root."""
    with pytest.raises(ImportError):
        exec(f"from quadkit.contracts.ai.relay import {name}")


def test_outbox_relay_protocol_untouched() -> None:
    """The unrelated event-outbox protocol remains available in contracts."""
    from quadkit.contracts.events import OutboxRelayProtocol  # noqa: F401

    assert OutboxRelayProtocol is not None