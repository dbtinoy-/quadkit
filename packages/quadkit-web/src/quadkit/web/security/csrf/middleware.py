"""ASGI middleware for CSRF protection with dual-mode support.

Supports two patterns:
1. Double-Submit Cookie (stateless, default) — the cookie carries an
   HMAC-signed, expiring token (``base64url("{iss}:{ts}:{nonce}") +
   "." + base64url(hmac)``) that must be echoed in the header.
2. Synchronizer Token (stateful, requires CacheBackendProtocol) — validates
   against a server-side token stored in cache.

Also issues (or rotates when stale) the CSRF cookie on safe methods
(GET/HEAD/OPTIONS). Paths in ``CSRFConfig.excluded_paths`` are skipped for
cookie-less requests; cookie-bearing requests on those paths are still
validated.

Fail-closed behavior: when ``CSRFConfig.secret_key`` is ``None`` in cookie
(double-submit) mode, unsafe requests are always rejected — the token cannot
be verified — while safe-method issuance still works (development UX).
Configure ``QK_WEB__SECURITY__CSRF__SECRET_KEY`` (required in production).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time
from typing import TYPE_CHECKING, Any, cast

from quadkit.logging import get_logger
from quadkit.validation import SecretStr
from quadkit.web.security.config import CSRFConfig

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from quadkit.contracts.infra.cache import CacheBackendProtocol

logger = get_logger(__name__)

_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

#: Issuer label embedded in every token (fixed per process/secret).
_TOKEN_ISSUER = "web"  # noqa: S105  # issuer label constant, not a credential


def _b64decode(data: str) -> bytes:
    """Decode unpadded URL-safe base64 (tokens are minted without padding)."""
    return base64.urlsafe_b64decode(data.encode() + b"=" * (-len(data) % 4))


class CSRFProtectionMiddleware:
    """ASGI middleware for CSRF protection.

    Supports both double-submit cookie and synchronizer token patterns.
    If a ``cache`` is provided, the synchronizer token pattern is used (more
    secure). Otherwise, the double-submit cookie pattern is used (stateless)
    with HMAC-signed, expiring tokens.

    Cookie issuance happens automatically on safe methods (GET/HEAD/OPTIONS)
    so that clients receive a token before submitting state-changing requests.
    Stale cookies (older than ``token_ttl``) are rotated on safe methods.
    Paths listed in ``CSRFConfig.excluded_paths`` are skipped entirely for
    cookie-less requests; cookie-bearing requests on those paths are still
    validated, so cookie-authenticated form posts cannot bypass CSRF.

    Example::

        app = ASGIApp()
        config = CSRFConfig(enabled=True, cookie_name="csrf_token",
                            secret_key="secret")
        csrf = CSRFProtectionMiddleware(app, config=config)

        # With cache for synchronizer pattern:
        csrf = CSRFProtectionMiddleware(app, config=config, cache=cache_backend)
    """

    def __init__(
        self,
        app: Callable[..., Awaitable[None]],
        config: CSRFConfig | None = None,
        cache: CacheBackendProtocol | None = None,
    ) -> None:
        """Initialize CSRF middleware.

        Args:
            app: The ASGI application to wrap.
            config: CSRF configuration. Uses defaults if not provided.
            cache: Optional cache backend for synchronizer token pattern.
        """
        self._app = app
        self._config = config or CSRFConfig()
        self._cache = cache
        self._exclude_content_types = [
            ct.lower() for ct in self._config.exclude_content_types
        ]
        self._exclude_auth_schemes = [
            s.lower() for s in self._config.exclude_auth_schemes
        ]

    # ------------------------------------------------------------------
    # Token encoding / signing
    # ------------------------------------------------------------------

    def _build_signed_token(self, timestamp: int) -> str | None:
        """Build a signed, expiring CSRF token.

        Returns:
            ``base64url("{iss}:{ts}:{nonce}") + "." + base64url(hmac)``,
            or ``None`` when no ``secret_key`` is configured (verification
            would be impossible).
        """
        raw_secret: SecretStr | str | None = self._config.secret_key
        secret: str | None = None
        if isinstance(raw_secret, SecretStr):
            secret = raw_secret.get_secret_value()
        elif raw_secret is not None:
            secret = raw_secret
        if not secret:
            return None
        nonce = secrets.token_hex(16)
        payload = f"{_TOKEN_ISSUER}:{timestamp}:{nonce}"
        encoded_payload = base64.urlsafe_b64encode(payload.encode()).rstrip(b"=")
        signature = hmac.new(secret.encode(), encoded_payload, hashlib.sha256).digest()
        encoded_sig = base64.urlsafe_b64encode(signature).rstrip(b"=")
        return f"{encoded_payload.decode()}.{encoded_sig.decode()}"

    def _parse_token(self, token: str) -> tuple[int, bytes] | None:
        """Split a token into (timestamp, encoded payload) or ``None``.

        Returns ``None`` for malformed tokens so callers can fail closed.
        """
        try:
            encoded_payload, _ = token.split(".", 1)
            payload = _b64decode(encoded_payload).decode()
            issuer, ts_part, _nonce = payload.split(":", 2)
            if issuer != _TOKEN_ISSUER:
                return None
            return int(ts_part), encoded_payload.encode()
        except (ValueError, TypeError, UnicodeDecodeError):
            return None

    def _is_stale(self, token: str, now: int) -> bool:
        """Return True when the token is missing, unparseable, or expired."""
        parsed = self._parse_token(token)
        if parsed is None:
            return True
        return now - parsed[0] > self._config.token_ttl

    def _expected_signature(self, encoded_payload: bytes) -> bytes:
        """Recompute the HMAC-SHA256 signature over the encoded payload."""
        raw_sig = self._config.secret_key
        secret: str = (
            raw_sig.get_secret_value()
            if isinstance(raw_sig, SecretStr)
            else (raw_sig or "")
        )
        assert secret is not None  # noqa: S101  # validated at boot
        return hmac.new(secret.encode(), encoded_payload, hashlib.sha256).digest()

    # ------------------------------------------------------------------
    # ASGI plumbing
    # ------------------------------------------------------------------

    def _cache_key(self, session_id: str) -> str:
        return f"csrf:sync:{session_id}"

    def _is_excluded(self, path: str) -> bool:
        return any(path.startswith(p) for p in self._config.excluded_paths)

    def _parse_cookies(self, scope: dict[str, Any]) -> dict[str, str]:
        cookies: dict[str, str] = {}
        for name, value in scope.get("headers", []):
            if name.lower() == b"cookie":
                for part in value.decode().split(";"):
                    part = part.strip()
                    if "=" in part:
                        k, v = part.split("=", 1)
                        cookies[k.strip()] = v.strip()
        return cookies

    def _get_header(self, scope: dict[str, Any], header_name: str) -> str | None:
        target = header_name.lower().encode()
        for name, value in scope.get("headers", []):
            if name.lower() == target:
                return cast("str", value.decode())
        return None

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Callable[[], Awaitable[dict[str, Any]]],
        send: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> None:
        """Process the request through CSRF validation.

        Args:
            scope: The ASGI scope dictionary.
            receive: The ASGI receive callable.
            send: The ASGI send callable.
        """
        if scope.get("type") != "http":
            await self._app(scope, receive, send)
            return

        path = scope.get("path", "")
        method = scope.get("method", "").upper()

        if self._is_excluded(path):
            if method in _SAFE_METHODS or not self._parse_cookies(scope):
                await self._app(scope, receive, send)
                return

        if method in _SAFE_METHODS:
            await self._handle_safe_method(scope, receive, send)
        else:
            await self._handle_unsafe_method(scope, receive, send)

    async def _handle_safe_method(
        self,
        scope: dict[str, Any],
        receive: Callable[[], Awaitable[dict[str, Any]]],
        send: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> None:
        """Issue or rotate a CSRF token on safe methods."""
        cookies = self._parse_cookies(scope)
        token_source = cookies.get(self._config.cookie_name)
        now = int(time.time())
        synchronizer = self._cache is not None

        issue_new = token_source is None
        if (
            not synchronizer
            and token_source is not None
            and self._is_stale(token_source, now)
        ):
            issue_new = True

        if issue_new:
            if synchronizer:
                token_source = secrets.token_urlsafe(32)
            else:
                token_source = self._build_signed_token(now) or secrets.token_urlsafe(
                    32
                )

        token = token_source
        if self._cache:
            cache_key = self._cache_key(cast("str", token_source))
            result = await self._cache.get(cache_key)
            cached = result.unwrap_or(None)
            if cached is not None:
                token = cached
            if token is None:
                token = secrets.token_urlsafe(32)
            await self._cache.set(cache_key, token, ttl=self._config.token_ttl)

        async def send_with_cookie(message: dict[str, Any]) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                if issue_new:
                    cookie_parts = [
                        f"{self._config.cookie_name}={token_source}",
                        f"Path={self._config.cookie_path}",
                        f"SameSite={self._config.cookie_samesite.capitalize()}",
                    ]
                    if not synchronizer:
                        cookie_parts.append(f"Max-Age={self._config.token_ttl}")
                    if self._config.cookie_domain:
                        cookie_parts.append(f"Domain={self._config.cookie_domain}")
                    if self._config.cookie_secure:
                        cookie_parts.append("Secure")
                    if self._config.cookie_httponly:
                        cookie_parts.append("HttpOnly")
                    headers.append((b"set-cookie", "; ".join(cookie_parts).encode()))
                # Expose the token in the response header so SPAs can read it
                headers.append(
                    (
                        self._config.header_name.lower().encode(),
                        cast("str", token).encode(),
                    )
                )
                message = {**message, "headers": headers}
            await send(message)

        await self._app(scope, receive, send_with_cookie)

    async def _handle_unsafe_method(
        self,
        scope: dict[str, Any],
        receive: Callable[[], Awaitable[dict[str, Any]]],
        send: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> None:
        """Validate CSRF token on unsafe methods."""
        # Programmatic API clients (JSON) — explicit opt-in only
        content_type = (
            (self._get_header(scope, "content-type") or "")
            .split(";")[0]
            .strip()
            .lower()
        )
        if content_type and content_type in self._exclude_content_types:
            await self._app(scope, receive, send)
            return

        # Token-authenticated clients don't need CSRF protection — explicit opt-in
        auth_header = self._get_header(scope, "authorization") or ""
        if auth_header:
            scheme = auth_header.split(" ", 1)[0].lower()
            if scheme in self._exclude_auth_schemes:
                await self._app(scope, receive, send)
                return

        cookies = self._parse_cookies(scope)
        token_source = cookies.get(self._config.cookie_name)
        header_token = self._get_header(scope, self._config.header_name)

        if not token_source or not header_token:
            await self._reject(scope, receive, send, "missing_token")
            return

        if self._cache:
            # Synchronizer mode — server-side comparison via the cache.
            stored_result = await self._cache.get(self._cache_key(token_source))
            stored = stored_result.unwrap_or(None)
            if not stored or not hmac.compare_digest(stored, header_token):
                await self._reject(scope, receive, send, "token_mismatch")
                return
            await self._app(scope, receive, send)
            return

        # Cookie (double-submit) mode — token must be signed, fresh, and
        # echoed verbatim.
        raw_verify = self._config.secret_key
        verify_secret: str | None = (
            raw_verify.get_secret_value()
            if isinstance(raw_verify, SecretStr)
            else raw_verify
        )
        if not verify_secret:
            # Without a signing secret the token cannot be verified — fail closed.
            await self._reject(scope, receive, send, "csrf_unverifiable")
            return

        if not hmac.compare_digest(token_source, header_token):
            await self._reject(scope, receive, send, "token_mismatch")
            return

        parsed = self._parse_token(token_source)
        if parsed is None:
            await self._reject(scope, receive, send, "token_invalid")
            return

        ts, encoded_payload = parsed
        if int(time.time()) - ts > self._config.token_ttl:
            await self._reject(scope, receive, send, "token_expired")
            return

        try:
            _, provided_sig = token_source.rsplit(".", 1)
            provided = _b64decode(provided_sig)
        except (ValueError, TypeError):
            await self._reject(scope, receive, send, "token_invalid")
            return

        if not hmac.compare_digest(provided, self._expected_signature(encoded_payload)):
            await self._reject(scope, receive, send, "token_invalid")
            return

        await self._app(scope, receive, send)

    async def _reject(
        self,
        scope: dict[str, Any],
        receive: Callable[[], Awaitable[dict[str, Any]]],
        send: Callable[[dict[str, Any]], Awaitable[None]],
        reason: str,
    ) -> None:
        logger.warning("security.csrf_violation", reason=reason)
        body = (
            f'{{"success": false, "error": {{"type": "csrf_error",'
            f' "message": "CSRF validation failed: {reason.replace("_", " ")}"}}}}'
        ).encode()
        await send(
            {
                "type": "http.response.start",
                "status": 403,
                "headers": [(b"content-type", b"application/json")],
            }
        )
        await send({"type": "http.response.body", "body": body})


__all__ = ["CSRFProtectionMiddleware"]
