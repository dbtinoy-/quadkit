"""Unit tests for security domain"""

from unittest.mock import AsyncMock, Mock

import pytest
from starlette.requests import Request

from quadkit.web.security.context import SecurityContext, get_security_context
from quadkit.web.security.guards import (
    AuthGuard,
    PermissionGuard,
    RoleGuard,
    use_guards,
)


class TestAuthGuard:
    """Test authentication guard"""

    @pytest.fixture
    def auth_guard(self):
        """Create auth guard"""
        return AuthGuard()

    def test_auth_guard_creation(self, auth_guard):
        """Test auth guard instantiation"""
        assert auth_guard is not None

    @pytest.mark.asyncio
    async def test_auth_guard_can_activate(self, auth_guard):
        """Test auth guard can activate.

        Uses ``Mock(spec=Request)``: an unspecced Mock satisfies the
        runtime-checkable ``ExecutionContextProtocol`` via attribute
        auto-creation, which would divert the guard down the
        ``context.request`` branch and mask the assertion.
        """
        request = Mock(spec=Request)
        request.state.user = Mock()
        request.state.user.is_authenticated = True

        can_activate = await auth_guard.can_activate(request)
        assert can_activate is True

    @pytest.mark.asyncio
    async def test_auth_guard_can_activate_unauthenticated(self, auth_guard):
        """Test auth guard blocks unauthenticated users"""
        request = Mock(spec=Request)
        request.state.user = None

        can_activate = await auth_guard.can_activate(request)
        assert can_activate is False


class TestRoleGuard:
    """Test role-based guard"""

    @pytest.fixture
    def mock_authorizer(self):
        """Create mock authorizer"""
        authorizer = AsyncMock()
        authorizer.check_access = AsyncMock(return_value=True)
        return authorizer

    @pytest.fixture
    def role_guard(self, mock_authorizer):
        """Create role guard"""
        return RoleGuard("admin", "moderator", authorizer=mock_authorizer)

    def test_role_guard_creation(self, role_guard):
        """Test role guard instantiation"""
        assert role_guard is not None
        assert "admin" in role_guard.required_roles
        assert "moderator" in role_guard.required_roles

    @pytest.mark.asyncio
    async def test_role_guard_has_required_role(self, role_guard, mock_authorizer):
        """Test role guard allows user with required role"""
        request = Mock()
        request.state.user = Mock()
        request.state.user.roles = ["admin", "user"]

        mock_authorizer.check_access = AsyncMock(return_value=True)

        can_activate = await role_guard.can_activate(request)
        assert can_activate is True

    @pytest.mark.asyncio
    async def test_role_guard_missing_role(self, role_guard, mock_authorizer):
        """Test role guard blocks user without required role"""
        request = Mock()
        request.state.user = Mock()
        request.state.user.roles = ["user"]

        mock_authorizer.check_access = AsyncMock(return_value=False)

        can_activate = await role_guard.can_activate(request)
        assert can_activate is False


class TestPermissionGuard:
    """Test permission-based guard"""

    @pytest.fixture
    def mock_authorizer(self):
        """Create mock authorizer"""
        authorizer = AsyncMock()
        authorizer.can = AsyncMock(return_value=True)
        return authorizer

    @pytest.fixture
    def permission_guard(self, mock_authorizer):
        """Create permission guard"""
        return PermissionGuard("read:users", "write:users", authorizer=mock_authorizer)

    def test_permission_guard_creation(self, permission_guard):
        """Test permission guard instantiation"""
        assert permission_guard is not None
        assert "read:users" in permission_guard.required_permissions
        assert "write:users" in permission_guard.required_permissions

    @pytest.mark.asyncio
    async def test_permission_guard_has_permission(
        self, permission_guard, mock_authorizer
    ):
        """Test permission guard allows user with required permission"""
        request = Mock()
        request.state.user = Mock()
        request.state.user.permissions = ["read:users", "write:users", "read:posts"]

        mock_authorizer.can = AsyncMock(return_value=True)

        can_activate = await permission_guard.can_activate(request)
        assert can_activate is True

    @pytest.mark.asyncio
    async def test_permission_guard_missing_permission(
        self, permission_guard, mock_authorizer
    ):
        """Test permission guard blocks user without required permission"""
        request = Mock()
        request.state.user = Mock()
        request.state.user.permissions = ["read:posts"]

        mock_authorizer.can = AsyncMock(return_value=False)

        can_activate = await permission_guard.can_activate(request)
        assert can_activate is False

    @pytest.mark.asyncio
    async def test_permission_guard_requires_all_by_default(self, mock_authorizer):
        """Multiple permissions default to AND (all required)."""
        mock_authorizer.can = AsyncMock(side_effect=[True, False])
        request = Mock()
        request.state.user = Mock()

        guard = PermissionGuard("users:read", "users:write", authorizer=mock_authorizer)
        can_activate = await guard.can_activate(request)
        assert can_activate is False

    @pytest.mark.asyncio
    async def test_permission_guard_require_all_false_uses_any(self, mock_authorizer):
        """require_all=False explicitly opts into OR semantics."""
        mock_authorizer.can = AsyncMock(side_effect=[True, False])
        request = Mock()
        request.state.user = Mock()

        guard = PermissionGuard(
            "users:read",
            "users:write",
            authorizer=mock_authorizer,
            require_all=False,
        )
        can_activate = await guard.can_activate(request)
        assert can_activate is True

    @pytest.mark.asyncio
    async def test_permission_guard_without_permissions_fails_closed(
        self, mock_authorizer
    ):
        """An empty required-permission set must never pass accidentally."""
        request = Mock()
        request.state.user = Mock()

        guard = PermissionGuard(authorizer=mock_authorizer)
        can_activate = await guard.can_activate(request)
        assert can_activate is False


class TestUseGuards:
    """Test guard decorator (use_guards)"""

    def test_use_guards_decorator(self):
        """Test use_guards decorator"""
        mock_authorizer = AsyncMock()

        @use_guards(AuthGuard, RoleGuard("admin", authorizer=mock_authorizer))
        def protected_route():
            return {"protected": True}

        assert hasattr(protected_route, "__guards__")
        assert len(protected_route.__guards__) == 2
        assert isinstance(protected_route.__guards__[0], AuthGuard)
        assert isinstance(protected_route.__guards__[1], RoleGuard)


class TestSecurityContext:
    """Test security context"""

    def test_security_context_creation(self):
        """Test security context instantiation"""
        user = Mock()
        user.id = "123"
        context = SecurityContext(user=user, roles=["admin"])
        assert context.user == user
        assert context.roles == ["admin"]

    def test_security_context_empty(self):
        """Test empty security context"""
        context = SecurityContext()
        assert context.user is None
        assert context.roles == []

    def test_security_context_properties(self):
        """Test security context properties"""
        user = Mock()
        context = SecurityContext(
            user=user,
            roles=["admin", "user"],
            permissions=["read", "write"],
        )
        assert context.is_authenticated is True
        assert context.has_role("admin") is True
        assert context.has_role("guest") is False
        assert context.has_permission("read") is True
        assert context.has_permission("delete") is False

    def test_get_security_context(self):
        """Test getting security context from request"""
        request = Mock()
        request.state.security = SecurityContext(user=Mock(), roles=["admin"])

        context = get_security_context(request)
        assert context.roles == ["admin"]
