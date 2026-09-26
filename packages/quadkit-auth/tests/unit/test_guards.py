"""Tests for authorization guards"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from quadkit.auth.authn.core import User
from quadkit.auth.authz.guards import (
    AuthorizationGuard,
    RouteGuard,
    optional_auth,
    require_auth,
    require_permissions,
    require_roles,
)
from quadkit import serialization as json


class TestAuthorizationGuard:
    """Test authorization guard"""

    def setup_method(self):
        """Setup test method"""
        self.guard = AuthorizationGuard(roles=["admin"], permissions=["write"])

    @pytest.mark.asyncio
    async def test_check_authorization_success(self):
        """Test successful authorization"""
        user = User(
            user_id="user123",
            name="testuser",
            email="test@example.com",
            roles=["admin", "user"],
            permissions=["read", "write"],
        )

        mock_service = Mock()
        mock_service.has_any_role = Mock(return_value=True)
        mock_service.can = AsyncMock(return_value=True)
        guard = AuthorizationGuard(roles=["admin"], permissions=["write"], auth_service=mock_service)
        assert await guard.check_authorization(user)

    @pytest.mark.asyncio
    async def test_check_authorization_no_user(self):
        """Test authorization with no user"""
        assert not await self.guard.check_authorization(None)

    @pytest.mark.asyncio
    async def test_check_authorization_inactive_user(self):
        """Test authorization with inactive user"""
        user = User(
            user_id="user123",
            name="testuser",
            email="test@example.com",
            is_active=False,
        )

        assert not await self.guard.check_authorization(user)

    @pytest.mark.asyncio
    async def test_check_authorization_missing_role(self):
        """Test authorization with missing role"""
        user = User(
            user_id="user123",
            name="testuser",
            email="test@example.com",
            roles=["user"],
            permissions=["read", "write"],
        )

        mock_service = Mock()
        mock_service.has_any_role = Mock(return_value=False)
        guard = AuthorizationGuard(roles=["admin"], permissions=["write"], auth_service=mock_service)
        assert not await guard.check_authorization(user)

    @pytest.mark.asyncio
    async def test_check_authorization_missing_permission(self):
        """Test authorization with missing permission"""
        user = User(
            user_id="user123",
            name="testuser",
            email="test@example.com",
            roles=["admin"],
            permissions=["read"],
        )

        mock_service = Mock()
        mock_service.has_any_role = Mock(return_value=True)
        mock_service.can = AsyncMock(return_value=False)
        guard = AuthorizationGuard(roles=["admin"], permissions=["write"], auth_service=mock_service)
        assert not await guard.check_authorization(user)

    def test_get_error_message_roles(self):
        """Test error message for role requirements"""
        guard = AuthorizationGuard(roles=["admin"])
        assert "Required roles: admin" in guard.get_error_message()

    def test_get_error_message_permissions(self):
        """Test error message for permission requirements"""
        guard = AuthorizationGuard(permissions=["write"])
        assert "Required permissions: write" in guard.get_error_message()

    def test_get_error_message_both(self):
        """Test error message for both roles and permissions"""
        guard = AuthorizationGuard(roles=["admin"], permissions=["write"])
        assert "Required roles: admin" in guard.get_error_message()


class TestRouteGuard:
    """Test route guard"""

    def setup_method(self):
        """Setup test method"""
        self.mock_service = Mock()
        self.mock_service.has_any_role = Mock(return_value=True)
        self.mock_service.can = AsyncMock(return_value=True)
        self.auth_guard = AuthorizationGuard(roles=["admin"], auth_service=self.mock_service)
        self.route_guard = RouteGuard(self.auth_guard)

    @pytest.mark.asyncio
    async def test_check_access_success(self):
        """Test successful access check"""
        user = User(
            user_id="user123",
            name="testuser",
            email="test@example.com",
            roles=["admin"],
        )

        self.mock_service.has_any_role = Mock(return_value=True)
        assert await self.route_guard.check_access(user)

    @pytest.mark.asyncio
    async def test_check_access_denied(self):
        """Test access denied"""
        user = User(
            user_id="user123",
            name="testuser",
            email="test@example.com",
            roles=["user"],
        )

        self.mock_service.has_any_role = Mock(return_value=False)
        assert not await self.route_guard.check_access(user)

    @pytest.mark.asyncio
    async def test_get_deny_response(self):
        """Test deny response generation"""
        response = await self.route_guard.get_deny_response()
        assert response.status_code == 403
        content = json.loads(response.body.decode())
        assert "forbidden" in content["error"]
        assert "Required roles: admin" in content["message"]


class Testrequire_authDecorator:
    """Test require_auth decorator"""

    def setup_method(self):
        """Setup test method"""
        self.mock_request = Mock()
        self.mock_request.state = Mock()
        self.mock_request.state.user = None
        self.mock_request.headers = {}

    def _make_mock_service(self, *, has_any_role: bool = True, can: bool = True) -> Mock:
        """Build a mock AuthorizationService."""
        svc = Mock()
        svc.has_any_role = Mock(return_value=has_any_role)
        svc.can = AsyncMock(return_value=can)
        return svc

    @pytest.mark.asyncio
    async def test_require_auth_success(self):
        """Test successful authentication and authorization"""
        user = User(
            user_id="user123",
            name="testuser",
            email="test@example.com",
            roles=["admin"],
        )
        self.mock_request.state.user = user

        @require_auth(roles=["admin"])
        async def test_handler(request):
            return {"success": True}

        mock_svc = self._make_mock_service(has_any_role=True)
        with patch("quadkit.auth.authz.guards.AuthorizationService", return_value=mock_svc):
            result = await test_handler(self.mock_request)
            assert result == {"success": True}

    @pytest.mark.asyncio
    async def test_require_auth_no_user(self):
        """Test authentication required but no user"""
        self.mock_request.state.user = None

        @require_auth()
        async def test_handler(request):
            return {"success": True}

        result = await test_handler(self.mock_request)
        assert result.status_code == 401
        content = json.loads(result.body.decode())
        assert "unauthorized" in content["error"]

    @pytest.mark.asyncio
    async def test_require_auth_forbidden(self):
        """Test authorization failed"""
        user = User(
            user_id="user123",
            name="testuser",
            email="test@example.com",
            roles=["user"],
        )
        self.mock_request.state.user = user

        @require_auth(roles=["admin"])
        async def test_handler(request):
            return {"success": True}

        mock_svc = self._make_mock_service(has_any_role=False)
        with patch("quadkit.auth.authz.guards.AuthorizationService", return_value=mock_svc):
            result = await test_handler(self.mock_request)
            assert result.status_code == 403
            content = json.loads(result.body.decode())
            assert "forbidden" in content["error"]

    @pytest.mark.asyncio
    async def test_require_auth_optional(self):
        """Test optional authentication"""
        self.mock_request.state.user = None

        @require_auth(optional=True)
        async def test_handler(request):
            return {"success": True}

        result = await test_handler(self.mock_request)
        assert result == {"success": True}

    @pytest.mark.asyncio
    async def test_require_roles_decorator(self):
        """Test require_roles decorator"""
        user = User(
            user_id="user123",
            name="testuser",
            email="test@example.com",
            roles=["admin"],
        )
        self.mock_request.state.user = user

        @require_roles("admin")
        async def test_handler(request):
            return {"success": True}

        mock_svc = self._make_mock_service(has_any_role=True)
        with patch("quadkit.auth.authz.guards.AuthorizationService", return_value=mock_svc):
            result = await test_handler(self.mock_request)
            assert result == {"success": True}

    @pytest.mark.asyncio
    async def test_require_permissions_decorator(self):
        """Test require_permissions decorator"""
        user = User(
            user_id="user123",
            name="testuser",
            email="test@example.com",
            permissions=["write"],
        )
        self.mock_request.state.user = user

        @require_permissions("write")
        async def test_handler(request):
            return {"success": True}

        mock_svc = self._make_mock_service(can=True)
        with patch("quadkit.auth.authz.guards.AuthorizationService", return_value=mock_svc):
            result = await test_handler(self.mock_request)
            assert result == {"success": True}

    @pytest.mark.asyncio
    async def test_optional_auth_decorator(self):
        """Test optional_auth decorator"""
        self.mock_request.state.user = None

        @optional_auth
        async def test_handler(request):
            return {"success": True}

        result = await test_handler(self.mock_request)
        assert result == {"success": True}

    @pytest.mark.asyncio
    async def test_require_auth_no_request_object(self):
        """Test require_auth with no request object in args"""

        @require_auth()
        async def test_handler():
            return {"success": True}

        with pytest.raises(ValueError, match="Could not find request object"):
            await test_handler()

    @pytest.mark.asyncio
    async def test_require_auth_request_in_kwargs(self):
        """Test require_auth with request in kwargs"""
        user = User(
            user_id="user123",
            name="testuser",
            email="test@example.com",
            roles=["admin"],
        )

        @require_auth(roles=["admin"])
        async def test_handler(request=None):
            return {"success": True}

        result = await test_handler(request=self.mock_request)
        # This will fail because request.state.user is not set, but the decorator found the request
        assert result.status_code == 401  # No user set
