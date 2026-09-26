"""Google OAuth verification and claim normalization helpers."""

from __future__ import annotations

from datetime import UTC, datetime
import inspect
from typing import TYPE_CHECKING, Any, cast

import jwt

from quadkit.auth.exceptions import OAuth2Error
from quadkit.contracts.auth import VerifiedIdentityClaims
from quadkit.contracts.web import HTTPClientProtocol
from quadkit.logging import get_logger
from quadkit.serialization import dumps

if TYPE_CHECKING:
    from quadkit.contracts.web import HttpResponse

logger = get_logger(__name__)

GOOGLE_ISSUERS: tuple[str, str] = (
    "https://accounts.google.com",
    "accounts.google.com",
)
GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


class GoogleOAuthService:
    """Verify Google OAuth tokens and normalize the verified claims."""

    def __init__(
        self,
        *,
        client_id: str,
        http_client: HTTPClientProtocol | None = None,
        jwks_url: str = GOOGLE_JWKS_URL,
        tokeninfo_url: str = GOOGLE_TOKENINFO_URL,
        userinfo_url: str = GOOGLE_USERINFO_URL,
        allowed_issuers: tuple[str, ...] = GOOGLE_ISSUERS,
        jwks_cache_ttl_seconds: int = 300,
    ) -> None:
        if not client_id:
            raise ValueError("Google OAuth client_id is required")
        self.client_id = client_id
        self.http_client = http_client
        self.jwks_url = jwks_url
        self.tokeninfo_url = tokeninfo_url
        self.userinfo_url = userinfo_url
        self.allowed_issuers = allowed_issuers
        self.jwks_cache_ttl_seconds = max(0, jwks_cache_ttl_seconds)
        self._jwks_cache: dict[str, Any] | None = None
        self._jwks_cached_at: datetime | None = None

    async def verify_token(self, token: str) -> VerifiedIdentityClaims:
        """Verify a Google token, preferring ID-token JWKS validation.

        Args:
            token: Google-issued ID token or access token.

        Returns:
            Normalized, verified Google identity claims.

        Raises:
            OAuth2Error: If the token cannot be verified or normalized.
        """
        if self._looks_like_jwt(token):
            try:
                return await self.verify_id_token(token)
            except OAuth2Error:
                raise
            except (jwt.PyJWTError, ValueError, KeyError) as exc:
                logger.debug("google_id_token_verification_failed", error=str(exc))
                raise OAuth2Error("Invalid Google ID token") from exc

        return await self.verify_userinfo_token(token)

    async def verify_id_token(self, token: str) -> VerifiedIdentityClaims:
        """Verify a Google ID token against Google's JWKS."""
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")
        alg = header.get("alg") or "RS256"

        # Never trust the token's self-declared algorithm: it comes from an
        # unverified header, and feeding it into PyJWT's allow-list would let
        # an unsigned ``alg: none`` token skip signature verification
        # entirely (authentication bypass). Google signs ID tokens with
        # RS256 only — pin it and reject anything else.
        if alg != "RS256":
            raise OAuth2Error(f"Unsupported Google token algorithm: {alg!r}")

        jwks = await self._get_jwks()
        key = self._select_jwk(jwks, kid)
        public_key: Any = jwt.algorithms.RSAAlgorithm.from_jwk(dumps(key).decode())

        try:
            payload = jwt.decode(
                token,
                key=public_key,
                algorithms=["RS256"],
                audience=self.client_id,
                options={
                    "require": ["exp", "iss", "sub", "aud"],
                },
            )
        except jwt.PyJWTError as exc:
            logger.warning(
                "google_id_token_decode_failed",
                error=str(exc),
                kid=kid,
            )
            raise OAuth2Error("Invalid Google ID token") from exc

        issuer = str(payload.get("iss") or "")
        if issuer not in self.allowed_issuers:
            raise OAuth2Error(f"Invalid Google token issuer: {issuer!r}")

        email_verified = bool(payload.get("email_verified", False))
        if not email_verified:
            raise OAuth2Error("Google email is not verified")

        return self._claims_from_payload(
            payload,
            issuer=issuer,
            audience=str(payload.get("aud") or self.client_id),
        )

    async def verify_userinfo_token(self, token: str) -> VerifiedIdentityClaims:
        """Verify a Google access token via the userinfo endpoint."""
        payload = await self._request_json(
            "GET",
            self.userinfo_url,
            headers={"Authorization": f"Bearer {token}"},
        )

        issuer = str(payload.get("iss") or "accounts.google.com")
        email_verified = bool(payload.get("email_verified", False))
        if not email_verified:
            raise OAuth2Error("Google email is not verified")

        return self._claims_from_payload(
            payload,
            issuer=issuer,
            audience=self.client_id,
        )

    async def verify_tokeninfo(self, token: str) -> VerifiedIdentityClaims:
        """Verify a Google token using the tokeninfo endpoint fallback."""
        payload = await self._request_json(
            "GET",
            self.tokeninfo_url,
            params={"id_token": token},
        )

        issuer = str(payload.get("iss") or "")
        if issuer and issuer not in self.allowed_issuers:
            raise OAuth2Error(f"Invalid Google token issuer: {issuer!r}")

        audience = str(payload.get("aud") or self.client_id)
        if audience != self.client_id:
            raise OAuth2Error("Google token audience mismatch")

        email_verified = payload.get("email_verified")
        if email_verified is not None and not bool(email_verified):
            raise OAuth2Error("Google email is not verified")

        return self._claims_from_payload(
            payload,
            issuer=issuer or None,
            audience=audience,
        )

    async def _get_jwks(self) -> dict[str, Any]:
        """Fetch Google's JWKS, caching it for a short TTL."""
        now = datetime.now(UTC)
        if (
            self._jwks_cache is not None
            and self._jwks_cached_at is not None
            and (now - self._jwks_cached_at).total_seconds()
            < self.jwks_cache_ttl_seconds
        ):
            return self._jwks_cache

        jwks = await self._request_json("GET", self.jwks_url)
        self._jwks_cache = jwks
        self._jwks_cached_at = now
        return jwks

    def _select_jwk(self, jwks: dict[str, Any], kid: str | None) -> dict[str, Any]:
        """Select the matching JWK for a token header."""
        keys = jwks.get("keys")
        if not isinstance(keys, list) or not keys:
            raise OAuth2Error("Google JWKS payload is empty")

        if kid:
            for key in keys:
                if isinstance(key, dict) and key.get("kid") == kid:
                    return key
            # A kid that matches no key is a hard failure — falling back to a
            # single unkeyed JWK would silently verify against the wrong key.
            raise OAuth2Error(f"No Google signing key found for kid {kid!r}")

        if len(keys) == 1 and isinstance(keys[0], dict):
            return cast("dict[str, Any]", keys[0])

        raise OAuth2Error("No matching Google signing key found")

    async def _request_json(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Fetch JSON via the injected HTTP client or a temporary httpx client."""
        if self.http_client is not None:
            response = await self.http_client.request(method, url, **kwargs)
            return await self._response_json(response)

        import httpx

        async with httpx.AsyncClient(timeout=10.0) as client:
            httpx_response = await client.request(method, url, **kwargs)
            httpx_response.raise_for_status()
            return cast("dict[str, Any]", httpx_response.json())

    async def _response_json(self, response: HttpResponse | Any) -> dict[str, Any]:
        """Normalise framework HTTP responses and test doubles to JSON dicts."""
        status = getattr(response, "status", None)
        if status is None:
            status = getattr(response, "status_code", None)
        if isinstance(status, int) and status >= 400:
            raise OAuth2Error(
                f"Google request failed with HTTP {status}",
            )

        payload = getattr(response, "json", None)
        if callable(payload):
            payload = payload()
        if inspect.isawaitable(payload):
            payload = await payload
        if not isinstance(payload, dict):
            raise OAuth2Error("Google response did not contain JSON")
        return cast("dict[str, Any]", payload)

    def _claims_from_payload(
        self,
        payload: dict[str, Any],
        *,
        issuer: str | None,
        audience: str | None,
    ) -> VerifiedIdentityClaims:
        """Convert Google payloads into normalized verified identity claims."""
        expires_at = self._timestamp_to_datetime(payload.get("exp"))
        issued_at = self._timestamp_to_datetime(payload.get("iat"))
        provider_user_id_raw = (
            payload.get("sub") or payload.get("id") or payload.get("provider_user_id")
        )
        if not provider_user_id_raw:
            raise OAuth2Error("Google payload did not include a subject identifier")
        provider_user_id = str(provider_user_id_raw)

        return VerifiedIdentityClaims(
            provider="google",
            provider_user_id=provider_user_id,
            email=payload.get("email"),
            email_verified=bool(payload.get("email_verified", False)),
            name=payload.get("name") or payload.get("given_name"),
            picture=payload.get("picture"),
            issuer=issuer,
            audience=audience,
            expires_at=expires_at,
            issued_at=issued_at,
            raw_data=dict(payload),
        )

    def _timestamp_to_datetime(self, value: Any) -> datetime | None:
        """Convert a numeric UNIX timestamp to UTC datetime."""
        if value is None:
            return None
        try:
            return datetime.fromtimestamp(float(value), tz=UTC)
        except (TypeError, ValueError, OSError):
            return None

    @staticmethod
    def _looks_like_jwt(token: str) -> bool:
        """Return True when the token resembles a JWT."""
        return token.count(".") == 2


__all__ = [
    "GOOGLE_ISSUERS",
    "GOOGLE_JWKS_URL",
    "GOOGLE_TOKENINFO_URL",
    "GOOGLE_USERINFO_URL",
    "GoogleOAuthService",
]
