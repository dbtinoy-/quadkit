"""Admin principal bridge types (spec D3)."""

from __future__ import annotations

from quadkit.contracts.admin import AdminPrincipal, AdminPrincipalProviderProtocol


def test_principal_fields() -> None:
    p = AdminPrincipal(
        user_id="u1",
        name="Ada",
        email="ada@example.com",
        roles=["superadmin"],
        permissions=[],
        is_active=True,
    )
    assert p.roles == ["superadmin"]


def test_protocol_members() -> None:
    required = {
        "principal_for",
        "list_principals",
        "create_principal",
        "update_principal",
        "delete_principal",
        "authenticate",
        "sync_roles",
        "ensure_schema",
    }
    assert required.issubset(set(AdminPrincipalProviderProtocol.__dict__))