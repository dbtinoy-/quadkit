"""AuthorizationService satisfies the union AuthorizerProtocol."""

from __future__ import annotations

import pytest

from quadkit.auth.authz.service import AuthorizationService


class _User:
    def __init__(self, user_id: str, roles: list[str], is_superuser: bool = False):
        self.user_id = user_id
        self.roles = roles
        self.is_superuser = is_superuser


@pytest.fixture
def service() -> AuthorizationService:
    svc = AuthorizationService()
    svc.set_roles({
        "editor": {"permissions": ["users.create", "users.update"]},
        "viewer": {"permissions": []},
        "superadmin": {"permissions": [], "is_system": True},
    })
    return svc


@pytest.mark.asyncio
async def test_can_create_granted(service: AuthorizationService) -> None:
    svc = service
    svc.register_role("editor", {"permissions": ["users.create"]})
    user = _User("u1", ["editor"])
    assert await svc.can_create(user, "users")


@pytest.mark.asyncio
async def test_can_create_denied_default(service: AuthorizationService) -> None:
    svc = service
    user = _User("u2", ["viewer"])
    assert not await svc.can_create(user, "users")


@pytest.mark.asyncio
async def test_can_update_with_record_ignored_for_now(service: AuthorizationService) -> None:
    svc = service
    svc.register_role("editor", {"permissions": ["users.update"]})
    user = _User("u3", ["editor"])
    assert await svc.can_update(user, "users", record=object())


@pytest.mark.asyncio
async def test_can_execute_action_permission_gate(service: AuthorizationService) -> None:
    svc = service
    svc.register_role("owner", {"permissions": ["notes.publish"]})
    user = _User("u4", ["owner"])
    assert await svc.can_execute_action(user, "notes", "publish")


@pytest.mark.asyncio
async def test_superadmin_bypass(service: AuthorizationService) -> None:
    svc = service
    admin = _User("root", ["superadmin"], is_superuser=True)
    assert await svc.can_delete(admin, "anything")


@pytest.mark.asyncio
async def test_can_keeps_original_shape(service: AuthorizationService) -> None:
    svc = service
    svc.register_role("viewer", {"permissions": ["notes.read"]})
    user = _User("u5", ["viewer"])
    assert await svc.can(user, "read", "notes")
