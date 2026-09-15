"""Union authorizer protocol completeness tests."""

from __future__ import annotations

import inspect

import pytest

from quadkit.contracts.auth import AuthorizerProtocol


def test_authorizer_protocol_has_union_methods() -> None:
    expected = {
        "authorize",
        "check_access",
        "can",
        "can_view",
        "can_create",
        "can_update",
        "can_delete",
        "can_execute_action",
        "set_roles",
        "register_role",
        "remove_role",
        "sync_from_db",
    }
    assert expected.issubset(set(AuthorizerProtocol.__dict__))


def test_can_keeps_positional_order_user_action_resource() -> None:
    sig = inspect.signature(AuthorizerProtocol.can)
    params = list(sig.parameters)
    assert params[1:4] == ["user", "action", "resource"]


def test_can_execute_action_keeps_user_resource_action_record() -> None:
    sig = inspect.signature(AuthorizerProtocol.can_execute_action)
    params = list(sig.parameters)
    assert params[1:5] == ["user", "resource", "action", "record"]


def test_admin_authorizer_protocol_is_deleted() -> None:
    import importlib

    importlib.invalidate_caches()
    with pytest.raises(ImportError):  # noqa: PT011
        from quadkit.contracts.admin.authorizer import (  # type: ignore[attr-defined]
            AdminAuthorizerProtocol,
        )