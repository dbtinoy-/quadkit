"""Unit tests for AuthorizationService.remove_role."""

from __future__ import annotations

from quadkit.auth.authz.service import AuthorizationService


def _service_with_roles() -> AuthorizationService:
    svc = AuthorizationService()
    svc.set_roles(
        {
            "admin": {"permissions": ["*"]},
            "editor": {"inherits": ["viewer"], "permissions": ["posts.edit"]},
            "viewer": {"permissions": ["posts.view"]},
        }
    )
    return svc


def test_remove_role_removes_definition() -> None:
    svc = _service_with_roles()

    svc.remove_role("editor")

    assert svc.get_role("editor") is None
    assert svc.get_role("viewer") is not None


def test_remove_role_clears_permission_cache() -> None:
    svc = _service_with_roles()
    assert svc.get_role_permissions("viewer") == {"posts.view"}

    svc.remove_role("viewer")

    assert svc.get_role_permissions("admin") == {"*"}


def test_remove_role_missing_name_is_noop() -> None:
    svc = _service_with_roles()

    svc.remove_role("ghost")

    assert svc.get_role("admin") is not None
    assert len(svc._roles) == 3
