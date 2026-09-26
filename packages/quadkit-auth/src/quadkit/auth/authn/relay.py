"""Relay gateway API-key verifier (new-api TokenAuth parity).

Application-level adapter binding quadkit-auth's ``APIKeyManager``
behind the framework's ``RelayAuthVerifierProtocol``, so the relay
gateway can enforce API-key auth on its inbound routes without ever
importing quadkit-auth.  Credential parsing follows new-api's
``TokenAuth`` middleware: Claude routes read ``x-api-key``, Gemini
routes read ``?key=`` then ``x-goog-api-key``, everything else falls
back to the ``Authorization`` bearer header; keys are trimmed of the
``sk-`` family prefix before validation.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from quadkit.auth.authn.apikeys import APIKeyManager
from quadkit.contracts.ai.relay import (
    RelayAuthError,
    RelayAuthIdentity,
)
from quadkit.contracts.core.result import Err, Ok, Result
from quadkit.logging import get_logger

logger = get_logger(__name__)

__all__ = ["RelayApiKeyVerifier"]


class RelayApiKeyVerifier:
    """Verify inbound relay keys through quadkit-auth's API key manager.

    The verifier parses credentials from the request in new-api's
    precedence order (path-scoped ``x-api-key`` / ``?key=`` /
    ``x-goog-api-key`` first, ``Authorization`` bearer last), normalizes
    the key, and delegates lookup to an injected
    :class:`~quadkit.auth.authn.apikeys.APIKeyManager`.  It never logs
    key material and never raises for a bad credential.

    Args:
        manager: The API key manager performing validation and hashing.
        user_status_checker: Optional async predicate over a key owner's
            user id; when provided the owner must pass it or the request
            is rejected as ``AUTH_USER_DISABLED``.  When ``None`` only
            key validity governs.
    """

    def __init__(
        self,
        manager: APIKeyManager,
        *,
        user_status_checker: Callable[[str], Awaitable[bool]] | None = None,
    ) -> None:
        """Initialise the verifier with the key manager and checks."""
        self._manager = manager
        self._user_status_checker = user_status_checker

    async def authenticate(
        self, request: object
    ) -> Result[RelayAuthIdentity, RelayAuthError]:
        """Verify the caller of an inbound relay request.

        Args:
            request: The inbound request; duck-typed for ``headers``,
                ``query_params``, ``path``, and ``client``.

        Returns:
            ``Ok(identity)`` with the key's user, token, and prefix on
            success; ``Err`` with ``AUTH_TOKEN_INVALID`` for missing or
            unknown keys and ``AUTH_USER_DISABLED`` for disabled owners.
        """
        headers = _as_dict(getattr(request, "headers", None))
        query = _as_dict(getattr(request, "query_params", None))
        path: str = getattr(request, "path", "") or ""

        raw_key = self._extract_key(headers, query, path)
        if not raw_key:
            return Err(RelayAuthError("AUTH_TOKEN_INVALID", "missing API key"))

        key = _normalize(raw_key)
        if not key:
            return Err(RelayAuthError("AUTH_TOKEN_INVALID", "missing API key"))

        client = getattr(request, "client", None)
        ip_address = getattr(client, "host", None) if client else None

        api_key = await self._manager.validate_key(key, ip_address=ip_address)
        if api_key is None:
            logger.warning("relay_auth_invalid_key", key_prefix=key[:8])
            return Err(RelayAuthError("AUTH_TOKEN_INVALID", "invalid API key"))

        if (
            self._user_status_checker is not None
            and not await self._user_status_checker(api_key.user_id)
        ):
            return Err(RelayAuthError("AUTH_USER_DISABLED", "user is disabled"))

        return Ok(
            RelayAuthIdentity(
                user_id=api_key.user_id,
                token_id=api_key.key_id,
                key_prefix=api_key.prefix,
            )
        )

    def _extract_key(
        self, headers: dict[str, str], query: dict[str, str], path: str
    ) -> str:
        """Return the raw key per new-api's precedence order."""
        if "/v1/messages" in path:
            return headers.get("x-api-key", "") or ""

        if path.startswith(("/v1beta/models", "/v1beta/openai/models", "/v1/models/")):
            key = query.get("key", "")
            if key:
                return key
            return headers.get("x-goog-api-key", "") or ""

        authorization = headers.get("authorization", "")
        if authorization.startswith(("Bearer ", "bearer ")):
            return authorization[7:].strip()
        return ""


def _as_dict(value: object) -> dict[str, str]:
    """Coerce a header/query mapping into a plain case-folded dict.

    Starlette headers and query params are case-insensitive mappings;
    extracting via a casefolded copy mirrors that behavior for the
    duck-typed request doubles used in tests.
    """
    pairs: dict[str, str] = {}
    for key, item in getattr(value, "items", list)() if value else []:
        if isinstance(key, str) and isinstance(item, str):
            pairs[key.casefold()] = item
    return pairs


def _normalize(raw_key: str) -> str:
    """Trim the ``sk-`` family prefix, keeping the first dash segment.

    Harmless for quadkit's ``sk_live_...`` keys (no leading dash) and
    makes OpenAI-style ``sk-abc-123`` keys validate against their first
    segment, mirroring new-api's ``TokenAuth``.
    """
    key = raw_key
    if key.startswith("sk-"):
        key = key[3:]
    return key.split("-", 1)[0].strip()
