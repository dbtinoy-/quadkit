"""Inbound relay authentication contracts.

The gateway itself never validates keys: a host binds a
``RelayAuthVerifierProtocol`` implementation (e.g. the the optional provider
adapter) through the container, and the gateway only calls it.  When no
verifier is bound the gateway stays open by default (``require_auth``
is opt-in at the config level).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from quadkit.contracts.core.result import Result


@dataclass(frozen=True, slots=True)
class RelayAuthIdentity:
    """Identity of an authenticated relay caller."""

    user_id: str
    token_id: str
    key_prefix: str = "sk_"


@dataclass(frozen=True, slots=True)
class RelayAuthError:
    """Rejection reason for an inbound relay request."""

    code: str
    message: str


@runtime_checkable
class RelayAuthVerifierProtocol(Protocol):
    """Verify the caller of an inbound relay request.

    The implementation is responsible for parsing credentials from any
    supported location (``Authorization``, ``x-api-key``,
    ``x-goog-api-key``, ``?key=``) and returning either an identity or
    a rejection reason.  It must never raise for a bad credential.
    """

    async def authenticate(
        self, request: object
    ) -> Result[RelayAuthIdentity, RelayAuthError]: ...
