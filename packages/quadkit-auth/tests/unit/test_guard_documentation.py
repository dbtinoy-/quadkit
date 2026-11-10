"""Auth declares documentation through Contracts, never through Web imports."""

from dataclasses import FrozenInstanceError

import pytest

from quadkit.auth.authz.guards import require_auth as require_authorized
from quadkit.auth.web import require_permissions, require_roles
from quadkit.auth.web.guards import (
    AuthGuard,
    require_admin,
    require_auth,
    require_permission,
    require_role,
    use_guards,
)
from quadkit.contracts.web.security_metadata import (
    HTTP_BEARER_DOCUMENTATION_ATTRIBUTE,
    HttpBearerDocumentation,
)


@pytest.mark.parametrize(
    "decorator",
    [
        require_auth(),
        require_admin(),
        require_role("editor"),
        require_permission("rows:write"),
        use_guards(AuthGuard()),
        require_roles("editor"),
        require_permissions("rows.read"),
        require_authorized(),
    ],
)
def test_authentication_guards_publish_typed_immutable_documentation(decorator) -> None:
    async def execute():
        pytest.fail("decoration must not execute a handler")

    wrapped = decorator(execute)
    metadata = getattr(wrapped, HTTP_BEARER_DOCUMENTATION_ATTRIBUTE)
    assert isinstance(metadata, HttpBearerDocumentation)
    assert metadata.scheme_name == "bearerAuth"
    with pytest.raises(FrozenInstanceError):
        metadata.scheme_name = "changed"


def test_custom_non_auth_guard_does_not_claim_bearer_credentials() -> None:
    class CustomGuard:
        async def can_activate(self, context):
            return True

        async def handle_rejection(self, context):
            return None

    async def execute():
        pass

    wrapped = use_guards(CustomGuard())(execute)
    assert not hasattr(wrapped, HTTP_BEARER_DOCUMENTATION_ATTRIBUTE)


def test_stacking_unrelated_guard_preserves_auth_declaration() -> None:
    async def execute():
        pass

    wrapped = use_guards()(require_auth()(execute))
    assert (
        getattr(wrapped, HTTP_BEARER_DOCUMENTATION_ATTRIBUTE)
        == HttpBearerDocumentation()
    )


def test_optional_authorization_does_not_require_bearer_credentials():
    async def execute():
        pass

    wrapped = require_authorized(optional=True)(execute)
    assert not hasattr(wrapped, HTTP_BEARER_DOCUMENTATION_ATTRIBUTE)


@pytest.mark.parametrize(
    "decorator",
    [
        require_roles("editor"),
        require_permissions("rows.read"),
        require_authorized(roles=["editor"], permissions=["rows.read"]),
    ],
)
@pytest.mark.asyncio
async def test_direct_authorization_403_declares_its_wire_envelope_only(decorator):
    from types import SimpleNamespace

    from quadkit import serialization as json

    async def execute(request):
        pytest.fail("Unauthorized handler executed")

    wrapped = decorator(execute)
    metadata = getattr(wrapped, HTTP_BEARER_DOCUMENTATION_ATTRIBUTE)
    assert len(metadata.rejections) == 1
    rejection = metadata.rejections[0]
    assert rejection.status_code == 403
    assert rejection.error == "forbidden"
    with pytest.raises(FrozenInstanceError):
        rejection.error = "changed"
    response = await wrapped(
        SimpleNamespace(
            state=SimpleNamespace(user=SimpleNamespace(is_active=False)), headers={}
        )
    )
    assert response.status_code == rejection.status_code
    assert response.media_type == "application/json"
    body = json.loads(response.body)
    assert body["error"] == rejection.error
    assert isinstance(body["message"], str)


@pytest.mark.parametrize(
    "decorator",
    [
        require_authorized(),
        require_roles(),
        require_permissions(),
        require_auth(),
        require_admin(),
        use_guards(AuthGuard()),
    ],
)
def test_no_rejection_shape_guessed_for_auth_only_or_replaceable_guards(decorator):
    async def execute():
        pass

    metadata = getattr(decorator(execute), HTTP_BEARER_DOCUMENTATION_ATTRIBUTE)
    assert metadata.rejections == ()


@pytest.mark.parametrize(
    "options",
    [
        {},
        {"roles": ("editor",)},
        {"permissions": ("rows.read",)},
        {"roles": ("editor",), "optional": True},
    ],
)
def test_native_documentation_factory_agrees_without_constructing_guards(
    monkeypatch, options
):
    from quadkit.auth.authz.guards import (
        AuthorizationGuard,
        authorization_documentation,
    )

    async def execute():
        pytest.fail("Documentation executed a handler")

    wrapped = require_authorized(**options)(execute)
    expected = getattr(wrapped, HTTP_BEARER_DOCUMENTATION_ATTRIBUTE, None)

    def forbidden(*args, **kwargs):
        pytest.fail("Documentation constructed or ran a guard")

    monkeypatch.setattr(AuthorizationGuard, "__init__", forbidden)
    monkeypatch.setattr(AuthorizationGuard, "check_authorization", forbidden)
    assert authorization_documentation(**options) == expected
