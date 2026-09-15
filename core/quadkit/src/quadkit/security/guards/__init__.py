"""GuardProtocol chain and decorator for authorization."""

from __future__ import annotations

from quadkit.security.guards.chain import GuardChainImpl
from quadkit.security.guards.decorator import use_guards

__all__ = ["GuardChainImpl", "use_guards"]
