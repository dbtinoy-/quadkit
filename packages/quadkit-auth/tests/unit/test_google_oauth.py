"""Tests for Google OAuth verification support."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from quadkit.auth.authn.google_oauth import GoogleOAuthService
from quadkit.auth.di.sub_providers.google_oauth_provider import GoogleOAuthProvider
from quadkit.auth.exceptions import OAuth2Error
from quadkit.contracts.auth import VerifiedIdentityClaims


class TestGoogleOAuthService:
    """Test the Google OAuth verification service."""

    @pytest.fixture
    def service(self) -> GoogleOAuthService:
        return GoogleOAuthService(client_id="google-client-id")

    @pytest.mark.asyncio
    async def test_verify_id_token_returns_verified_claims(
        self,
        mocker,
        service: GoogleOAuthService,
    ) -> None:
        mocker.patch(
            "quadkit.auth.authn.google_oauth.jwt.get_unverified_header",
            return_value={"kid": "kid-1", "alg": "RS256"},
        )
        with (
            patch.object(
                service,
                "_get_jwks",
                new=AsyncMock(
                    return_value={
                        "keys": [
                            {
                                "kid": "kid-1",
                                "kty": "RSA",
                                "n": "abc",
                                "e": "AQAB",
                            },
                        ],
                    },
                ),
            ),
            patch(
                "quadkit.auth.authn.google_oauth.jwt.algorithms.RSAAlgorithm.from_jwk",
                return_value="public-key",
            ),
            patch(
                "quadkit.auth.authn.google_oauth.jwt.decode",
                return_value={
                    "sub": "google-sub",
                    "email": "user@example.com",
                    "email_verified": True,
                    "name": "Google User",
                    "picture": "https://example.com/avatar.png",
                    "iss": "https://accounts.google.com",
                    "aud": "google-client-id",
                    "exp": 1_800_000_000,
                    "iat": 1_700_000_000,
                },
            ),
        ):
            claims = await service.verify_id_token("header.payload.signature")

        assert isinstance(claims, VerifiedIdentityClaims)
        assert claims.provider == "google"
        assert claims.provider_user_id == "google-sub"
        assert claims.email == "user@example.com"
        assert claims.email_verified is True
        assert claims.name == "Google User"
        assert claims.picture == "https://example.com/avatar.png"
        assert claims.audience == "google-client-id"
        assert claims.issuer == "https://accounts.google.com"
        assert claims.raw_data["sub"] == "google-sub"

    @pytest.mark.asyncio
    async def test_verify_token_falls_back_to_userinfo_for_opaque_token(
        self,
        service: GoogleOAuthService,
    ) -> None:
        mock_http_client = AsyncMock()
        response = MagicMock()
        response.status = 200
        response.json = {
            "sub": "userinfo-sub",
            "email": "userinfo@example.com",
            "email_verified": True,
            "name": "User Info",
            "picture": "https://example.com/userinfo.png",
        }
        mock_http_client.request.return_value = response
        service.http_client = mock_http_client

        claims = await service.verify_token("opaque-access-token")

        mock_http_client.request.assert_called_once()
        assert claims.provider_user_id == "userinfo-sub"
        assert claims.email == "userinfo@example.com"
        assert claims.name == "User Info"
        assert claims.picture == "https://example.com/userinfo.png"

    @pytest.mark.asyncio
    async def test_verify_id_token_rejects_unverified_email(
        self,
        mocker,
        service: GoogleOAuthService,
    ) -> None:
        mocker.patch(
            "quadkit.auth.authn.google_oauth.jwt.get_unverified_header",
            return_value={"kid": "kid-1", "alg": "RS256"},
        )
        with (
            patch.object(
                service,
                "_get_jwks",
                new=AsyncMock(
                    return_value={
                        "keys": [
                            {
                                "kid": "kid-1",
                                "kty": "RSA",
                                "n": "abc",
                                "e": "AQAB",
                            },
                        ],
                    },
                ),
            ),
            patch(
                "quadkit.auth.authn.google_oauth.jwt.algorithms.RSAAlgorithm.from_jwk",
                return_value="public-key",
            ),
            patch(
                "quadkit.auth.authn.google_oauth.jwt.decode",
                return_value={
                    "sub": "google-sub",
                    "email": "user@example.com",
                    "email_verified": False,
                    "iss": "https://accounts.google.com",
                    "aud": "google-client-id",
                    "exp": 1_800_000_000,
                    "iat": 1_700_000_000,
                },
            ),
        ):
            with pytest.raises(OAuth2Error, match="Google email is not verified"):
                await service.verify_id_token("header.payload.signature")


class TestGoogleOAuthProvider:
    """Test Google OAuth provider registration."""

    @pytest.mark.asyncio
    async def test_registers_service(self) -> None:
        provider = GoogleOAuthProvider(
            google_oauth={
                "client_id": "google-client-id",
                "jwks_url": "https://example.com/jwks",
                "userinfo_url": "https://example.com/userinfo",
            },
        )

        class _Container:
            def __init__(self) -> None:
                self.registered: dict[Any, Any] = {}

            def singleton(self, key: Any, value: Any) -> None:
                self.registered[key] = value

        container = _Container()
        await provider.register(container)

        assert GoogleOAuthService in container.registered
        service = container.registered[GoogleOAuthService]()
        assert isinstance(service, GoogleOAuthService)
        assert service.client_id == "google-client-id"
        assert service.jwks_url == "https://example.com/jwks"
        assert service.userinfo_url == "https://example.com/userinfo"


class TestGoogleIdTokenAlgorithmPinning:
    """The token's self-declared alg must never reach PyJWT's allow-list."""

    @pytest.fixture
    def service(self) -> GoogleOAuthService:
        return GoogleOAuthService(client_id="google-client-id")

    def _jwks(self) -> dict[str, Any]:
        return {
            "keys": [
                {
                    "kid": "kid-1",
                    "kty": "RSA",
                    "n": "abc",
                    "e": "AQAB",
                },
            ],
        }

    @pytest.mark.asyncio
    async def test_alg_none_header_rejected(
        self, mocker, service: GoogleOAuthService
    ) -> None:
        """An unsigned token (alg: none) must be rejected before decode."""
        mocker.patch(
            "quadkit.auth.authn.google_oauth.jwt.get_unverified_header",
            return_value={"kid": "kid-1", "alg": "none"},
        )
        decode = mocker.patch(
            "quadkit.auth.authn.google_oauth.jwt.decode",
        )
        with pytest.raises(OAuth2Error, match="Unsupported Google token algorithm"):
            await service.verify_id_token("header.payload.")
        decode.assert_not_called()

    @pytest.mark.asyncio
    async def test_hs256_header_rejected(
        self, mocker, service: GoogleOAuthService
    ) -> None:
        """HMAC tokens are not Google ID tokens and must be rejected."""
        mocker.patch(
            "quadkit.auth.authn.google_oauth.jwt.get_unverified_header",
            return_value={"kid": "kid-1", "alg": "HS256"},
        )
        with pytest.raises(OAuth2Error, match="HS256"):
            await service.verify_id_token("header.payload.signature")

    @pytest.mark.asyncio
    async def test_rs256_is_pinned_in_decode(
        self, mocker, service: GoogleOAuthService
    ) -> None:
        """Even for a well-formed header, decode is pinned to RS256."""
        mocker.patch(
            "quadkit.auth.authn.google_oauth.jwt.get_unverified_header",
            return_value={"kid": "kid-1", "alg": "RS256"},
        )
        mocker.patch(
            "quadkit.auth.authn.google_oauth.GoogleOAuthService._get_jwks",
            new=AsyncMock(return_value=self._jwks()),
        )
        mocker.patch(
            "quadkit.auth.authn.google_oauth.jwt.algorithms.RSAAlgorithm.from_jwk",
            return_value="public-key",
        )
        decode = mocker.patch(
            "quadkit.auth.authn.google_oauth.jwt.decode",
            return_value={
                "sub": "google-sub",
                "email": "user@example.com",
                "email_verified": True,
                "iss": "https://accounts.google.com",
                "aud": "google-client-id",
                "exp": 1_800_000_000,
                "iat": 1_700_000_000,
            },
        )
        await service.verify_id_token("header.payload.signature")
        decode.assert_called_once()
        assert decode.call_args.kwargs["algorithms"] == ["RS256"]


class TestGoogleJwkSelection:
    """JWK selection must be strict about the kid header."""

    def test_mismatched_kid_fails_even_with_single_key(self) -> None:
        service = GoogleOAuthService(client_id="google-client-id")
        with pytest.raises(OAuth2Error, match="kid"):
            service._select_jwk({"keys": [{"kid": "a"}]}, "b")

    def test_single_key_used_when_no_kid(self) -> None:
        service = GoogleOAuthService(client_id="google-client-id")
        key = {"kid": "a"}
        assert service._select_jwk({"keys": [key]}, None) is key

    def test_matching_kid_wins(self) -> None:
        service = GoogleOAuthService(client_id="google-client-id")
        key = {"kid": "b"}
        assert service._select_jwk({"keys": [{"kid": "a"}, key]}, "b") is key

    def test_empty_jwks_fails(self) -> None:
        service = GoogleOAuthService(client_id="google-client-id")
        with pytest.raises(OAuth2Error, match="empty"):
            service._select_jwk({"keys": []}, None)
