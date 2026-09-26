"""Tests for SessionValidator."""

from __future__ import annotations

from quadkit.auth.web.middleware.session_validator import SessionValidator


class _Config:
    def __init__(
        self,
        roles_required: tuple[str, ...] | list[str] | None = None,
        permissions_required: tuple[str, ...] | list[str] | None = None,
        exclude_paths: list[str] | None = None,
        exclude_prefixes: list[str] | None = None,
    ) -> None:
        self.roles_required = roles_required
        self.permissions_required = permissions_required
        self.exclude_paths = exclude_paths or []
        self.exclude_prefixes = exclude_prefixes or []


class _Provider:
    def __init__(self, roles: set[str] | None = None, perms: set[str] | None = None) -> None:
        self._roles = roles or set()
        self._perms = perms or set()

    def has_any_role(self, user, required) -> bool:
        return bool(self._roles & set(required))

    def has_any_permission(self, user, required) -> bool:
        return bool(self._perms & set(required))


class _User:
    def __init__(self, active: bool = True) -> None:
        self.is_active = active


class TestCheckAuthorization:
    def test_none_user_rejected(self) -> None:
        v = SessionValidator(_Config(), _Provider())
        assert v.check_authorization(None) is False  # type: ignore[arg-type]

    def test_inactive_user_rejected(self) -> None:
        v = SessionValidator(_Config(), _Provider())
        assert v.check_authorization(_User(active=False)) is False

    def test_active_user_no_requirements(self) -> None:
        v = SessionValidator(_Config(), _Provider())
        assert v.check_authorization(_User()) is True

    def test_roles_required_met(self) -> None:
        v = SessionValidator(_Config(roles_required=["admin"]), _Provider(roles={"admin"}))
        assert v.check_authorization(_User()) is True

    def test_roles_required_missing(self) -> None:
        v = SessionValidator(_Config(roles_required=["admin"]), _Provider(roles={"user"}))
        assert v.check_authorization(_User()) is False

    def test_permissions_required_met(self) -> None:
        v = SessionValidator(
            _Config(permissions_required=["users:write"]), _Provider(perms={"users:write"})
        )
        assert v.check_authorization(_User()) is True

    def test_permissions_required_missing(self) -> None:
        v = SessionValidator(
            _Config(permissions_required=["users:write"]), _Provider(perms={})
        )
        assert v.check_authorization(_User()) is False

    def test_roles_and_permissions_combined(self) -> None:
        config = _Config(roles_required=["admin"], permissions_required=["x:y"])
        v = SessionValidator(config, _Provider(roles={"admin"}, perms={"x:y"}))
        assert v.check_authorization(_User()) is True

    def test_roles_met_permissions_missing(self) -> None:
        config = _Config(roles_required=["admin"], permissions_required=["x:y"])
        v = SessionValidator(config, _Provider(roles={"admin"}))
        assert v.check_authorization(_User()) is False


class TestShouldSkipAuth:
    def test_exact_exclude_path(self) -> None:
        v = SessionValidator(_Config(exclude_paths=["/health"]), _Provider())
        assert v.should_skip_auth("/health") is True
        assert v.should_skip_auth("/health/deep") is False

    def test_exclude_prefix(self) -> None:
        v = SessionValidator(_Config(exclude_prefixes=["/public/"]), _Provider())
        assert v.should_skip_auth("/public/img/logo.png") is True
        assert v.should_skip_auth("/private/img") is False

    def test_no_match(self) -> None:
        v = SessionValidator(_Config(), _Provider())
        assert v.should_skip_auth("/api/data") is False

    def test_multiple_prefixes(self) -> None:
        config = _Config(exclude_paths=["/health"], exclude_prefixes=["/static/", "/docs/"])
        v = SessionValidator(config, _Provider())
        assert v.should_skip_auth("/health") is True
        assert v.should_skip_auth("/static/app.js") is True
        assert v.should_skip_auth("/docs/index.html") is True
        assert v.should_skip_auth("/api") is False
