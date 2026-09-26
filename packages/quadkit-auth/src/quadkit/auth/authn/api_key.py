"""API Key AuthenticatorProtocol for Quadkit Auth.

Authenticates incoming requests by extracting an API key from the
``X-API-Key`` request header or the ``api_key`` query parameter, then
delegating validation to a configurable lookup function or static dict.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from quadkit.auth.exceptions import AuthenticationError
from quadkit.auth.models.user import User
from quadkit.logging import get_logger

if TYPE_CHECKING:
    from quadkit.result import Result

logger = get_logger(__name__)

# A lookup can be a plain dict mapping key → User, or an async/sync callable
# that accepts the raw key string and returns a User or None.
LookupCallable = Callable[[str], Awaitable[User | None] | (User | None)]


@dataclass
class APIKeyConfig:
    """Configuration for :class:`APIKeyAuthenticator`.

    Attributes:
        header_name: HTTP header to inspect for the API key.
            Defaults to ``"X-API-Key"``.
        query_param: URL query parameter name to fall back to when the header
            is absent.  Defaults to ``"api_key"``.
        lookup: Either a ``dict[str, User]`` mapping raw key strings to their
            owners, or an async/sync callable that accepts the raw key and
            returns ``User | None``.  This field is **required**.
    """

    lookup: LookupCallable | dict[str, Any]
    header_name: str = "X-API-Key"
    query_param: str = "api_key"
    # Injected via field so subclasses can override without touching __init__
    _lookup_is_dict: bool = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._lookup_is_dict = isinstance(self.lookup, dict)


class APIKeyAuthenticator:
    """Authenticates requests by validating an API key.

    Key extraction order:
    1. ``request_context["headers"][config.header_name]``
    2. ``request_context["query_params"][config.query_param]``

    If the key is absent **or** the lookup returns ``None`` an
    ``Err(AuthenticationError)`` is returned.  On success ``Ok(User)``
    is returned.

    Example::

        config = APIKeyConfig(
            lookup={"sk_live_abc123": admin_user},
        )
        authenticator = APIKeyAuthenticator(config)

        result = await authenticator.authenticate({
            "headers": {"X-API-Key": "sk_live_abc123"},
            "query_params": {},
        })

        if result.is_ok():
            user = result.unwrap()
    """

    def __init__(self, config: APIKeyConfig) -> None:
        """Initialise the authenticator.

        Args:
            config: Key-extraction and lookup configuration.
        """
        self._config = config

    def _extract_key(self, request_context: dict[str, Any]) -> str | None:
        """Extract the raw API key from the request context.

        Checks the configured header first, then falls back to the query
        parameter.  Header matching is case-insensitive.

        Args:
            request_context: Mapping with optional ``"headers"`` and
                ``"query_params"`` sub-dicts.

        Returns:
            Raw key string, or ``None`` if not present.
        """
        headers: dict[str, str] = request_context.get("headers") or {}
        query_params: dict[str, str] = request_context.get("query_params") or {}

        # Case-insensitive header lookup
        header_name_lower = self._config.header_name.lower()
        for name, value in headers.items():
            if name.lower() == header_name_lower:
                return value or None

        return query_params.get(self._config.query_param) or None

    async def _resolve_user(self, raw_key: str) -> User | None:
        """Invoke the configured lookup to resolve the user.

        Args:
            raw_key: Plain-text API key submitted by the caller.

        Returns:
            :class:`~quadkit.auth.models.user.User` if found, ``None``
            otherwise.
        """
        import inspect

        lookup = self._config.lookup

        if self._config._lookup_is_dict:
            return lookup.get(raw_key)  # type: ignore[union-attr]

        result = lookup(raw_key)  # type: ignore[operator]
        if inspect.isawaitable(result):
            return await result
        return result

    async def authenticate(
        self,
        request_context: dict[str, Any],
    ) -> Result[User, AuthenticationError]:
        """Authenticate a request using its API key.

        Args:
            request_context: A mapping that **must** contain at least one of:

                * ``"headers"``: ``dict[str, str]`` of HTTP request headers.
                * ``"query_params"``: ``dict[str, str]`` of URL query params.

        Returns:
            ``Ok(User)`` when a valid API key is found.
            ``Err(AuthenticationError)`` when the key is absent, invalid, or
            the lookup returns ``None``.
        """
        from quadkit.result import Err, Ok

        raw_key = self._extract_key(request_context)
        if not raw_key:
            logger.debug("api_key_missing", context_keys=list(request_context.keys()))
            return Err(AuthenticationError("API key is missing from the request"))

        user = await self._resolve_user(raw_key)
        if user is None:
            # Never log any part of the key: even a short prefix leaks key
            # material on every failed attempt (enumeration). A SHA-256
            # fingerprint keeps failures correlatable without disclosure.
            import hashlib

            logger.warning(
                "api_key_invalid",
                key_fingerprint=hashlib.sha256(raw_key.encode()).hexdigest()[:16],
            )
            return Err(AuthenticationError("Invalid or unrecognised API key"))

        logger.info(
            "api_key_authenticated",
            user_id=getattr(user, "user_id", None),
        )
        return Ok(user)


__all__ = ["APIKeyAuthenticator", "APIKeyConfig"]
