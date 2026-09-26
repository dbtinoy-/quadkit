"""OAuth2 identity-provider session and response tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from quadkit.auth.authn.oauth2 import (
    QuadkitConnectResponse,
    QuadkitConnectSession,
    OAuth2AuthProvider,
    OAuth2Manager,
    OAuth2IdentityProvider,
    OAuth2UserInfo,
)



class TestOAuth2IdentityProvider:
    """Test OAuth2 provider configuration"""

    def test_provider_creation(self):
        """Test OAuth2 provider creation"""
        provider = OAuth2IdentityProvider(
            name="google",
            client_id="test_client_id",
            client_secret="test_client_secret",
            authorize_url="https://accounts.google.com/oauth/authorize",
            access_token_url="https://oauth2.googleapis.com/token",
            userinfo_url="https://openidconnect.googleapis.com/v1/userinfo",
            scope="openid email profile",
        )

        assert provider.name == "google"
        assert provider.client_id == "test_client_id"
        assert provider.client_secret == "test_client_secret"
        assert provider.authorize_url == "https://accounts.google.com/oauth/authorize"
        assert provider.access_token_url == "https://oauth2.googleapis.com/token"
        assert (
            provider.userinfo_url == "https://openidconnect.googleapis.com/v1/userinfo"
        )
        assert provider.scope == "openid email profile"


class TestQuadkitConnectSession:
    """Test QuadkitConnect session adapter"""

    def setup_method(self):
        """Setup test method"""
        self.mock_http_client = AsyncMock()
        self.session = QuadkitConnectSession(self.mock_http_client)

    @pytest.mark.asyncio
    async def test_request_get(self):
        """Test GET request"""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.headers = {"content-type": "application/json"}
        self.mock_http_client.get.return_value = mock_response

        response = await self.session.get("https://example.com/api")
        assert isinstance(response, QuadkitConnectResponse)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_request_post(self):
        """Test POST request"""
        mock_response = MagicMock()
        mock_response.status = 201
        self.mock_http_client.post.return_value = mock_response

        response = await self.session.post(
            "https://example.com/api", data={"key": "value"},
        )
        assert isinstance(response, QuadkitConnectResponse)
        assert response.status_code == 201


class TestQuadkitConnectResponse:
    """Test QuadkitConnect response adapter"""

    def setup_method(self):
        """Setup test method"""
        self.mock_response = MagicMock()
        self.mock_response.status = 200
        self.mock_response.headers = {"content-type": "application/json"}
        self.response = QuadkitConnectResponse(self.mock_response)

    def test_status_code(self):
        """Test status code property"""
        assert self.response.status_code == 200

    def test_headers(self):
        """Test headers property"""
        assert self.response.headers == {"content-type": "application/json"}

    @pytest.mark.asyncio
    async def test_json(self):
        """Test JSON parsing"""

        async def mock_json():
            return {"user": "test"}

        self.mock_response.json = mock_json
        result = await self.response.json()
        assert result == {"user": "test"}

    @pytest.mark.asyncio
    async def test_text(self):
        """Test text content"""

        async def mock_text():
            return "Hello World"

        self.mock_response.text = mock_text
        result = await self.response.text()
        assert result == "Hello World"

    def test_raise_for_status(self):
        """Test raise for status"""
        self.response.raise_for_status()
        # Should not raise for 200 status


