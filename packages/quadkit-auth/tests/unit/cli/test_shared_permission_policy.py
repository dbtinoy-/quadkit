"""Generated native policy behavior, not transport or Builder activation proof."""

from __future__ import annotations

import importlib.util
import sys
from types import SimpleNamespace

import pytest

from quadkit.auth.authz.service import AuthorizationService
from quadkit.auth.cli.generators.auth_policy import AuthPolicyGenerator
from quadkit.auth.storage import SQLUserStore
from quadkit.sql.providers.sqlite_provider import SQLiteProvider

SPEC = {
    "mode": "shared_authenticated",
    "required_permission": "posts.categorize",
    "resources": ["post", "category"],
}


def _load(tmp_path, spec=SPEC):
    AuthPolicyGenerator(tmp_path).generate("assign_category", spec=spec)
    path = tmp_path / "assign_category_policy.py"
    module_spec = importlib.util.spec_from_file_location(
        "generated_shared_policy", path
    )
    assert module_spec is not None
    assert module_spec.loader is not None
    module = importlib.util.module_from_spec(module_spec)
    sys.modules[module_spec.name] = module
    module_spec.loader.exec_module(module)
    return module


@pytest.mark.asyncio
async def test_real_sql_account_permission_revocation_and_deactivation(tmp_path):
    generated = _load(tmp_path)
    database = SQLiteProvider(str(tmp_path / "accounts.db"))
    await database.connect()
    try:
        users = SQLUserStore(database)
        await users.initialize()
        user = await users.create_user(
            name="Editor",
            email="editor@example.test",
            hashed_password=None,
            permissions=["posts.categorize"],
        )
        # A test authority facade over real SQL accounts; production receives the
        # already registered native AuthProviderProtocol, not a new adapter.
        authorization = AuthorizationService()
        authority = SimpleNamespace(
            get_user=users.get_user_by_id,
            has_any_permission=authorization.has_any_permission,
        )
        policy = generated.AssignCategoryPolicy(authority)
        actor = SimpleNamespace(user_id=user.user_id, is_active=True, permissions=["*"])
        assert (await policy.evaluate(actor, "category")).allowed
        assert (await policy.evaluate(actor, "post")).allowed
        assert not (await policy.evaluate(actor, "private_record")).allowed
        user.permissions = []
        await users.update_user(user)
        # Forged/stale claims on the subject cannot replace current authority.
        assert not (await policy.evaluate(actor, "category")).allowed
        # Native role evaluation (not User.has_permission list membership).
        authorization.set_roles(
            {"catalog_editor": {"permissions": ["posts.categorize"]}}
        )
        user.roles = ["catalog_editor"]
        await users.update_user(user)
        assert (await policy.evaluate(actor, "category")).allowed
        user.roles = []
        await users.update_user(user)
        assert not (await policy.evaluate(actor, "category")).allowed
        user.permissions = ["posts.categorize"]
        user.is_active = False
        await users.update_user(user)
        assert not (await policy.evaluate(actor, "category")).allowed
    finally:
        await database.disconnect()


@pytest.mark.asyncio
async def test_denials_and_authority_failures_do_not_fallback(tmp_path):
    generated = _load(tmp_path)
    user = SimpleNamespace(user_id="editor", is_active=True)
    actor = SimpleNamespace(user_id="editor", is_active=True)
    seen = []

    async def get_user(subject):
        seen.append(subject)
        return user

    authority = SimpleNamespace(
        get_user=get_user, has_any_permission=lambda _user, _permissions: True
    )
    policy = generated.AssignCategoryPolicy(authority)
    for invalid in (
        None,
        SimpleNamespace(user_id="editor", is_active=False),
        SimpleNamespace(user_id="", is_active=True),
        SimpleNamespace(user_id=" editor", is_active=True),
    ):
        assert not (await policy.evaluate(invalid, "category")).allowed
    assert seen == []
    assert not (await policy.evaluate(actor, {"resource": "category"})).allowed
    assert seen == []
    user.user_id = "someone-else"
    assert not (await policy.evaluate(actor, "category")).allowed
    user.user_id = "editor"
    authority.has_any_permission = lambda _user, _permissions: 1
    assert not (await policy.evaluate(actor, "category")).allowed

    async def broken(_subject):
        raise RuntimeError("authority offline")

    authority.get_user = broken
    with pytest.raises(RuntimeError, match="authority offline"):
        await policy.evaluate(actor, "category")
    with pytest.raises(ValueError, match="authority"):
        generated.AssignCategoryPolicy(None)


@pytest.mark.asyncio
async def test_inflight_subject_drift_is_refused(tmp_path):
    generated = _load(tmp_path)
    actor = SimpleNamespace(user_id="editor", is_active=True)

    async def get_user(subject):
        actor.user_id = "changed"
        return SimpleNamespace(user_id=subject, is_active=True)

    policy = generated.AssignCategoryPolicy(
        SimpleNamespace(get_user=get_user, has_any_permission=lambda _u, _p: True)
    )
    assert not (await policy.evaluate(actor, "category")).allowed


@pytest.mark.parametrize(
    "spec",
    [
        {},
        {**SPEC, "mode": "owner"},
        {**SPEC, "required_permission": "*"},
        {**SPEC, "required_permission": "posts categorize"},
        {**SPEC, "required_permission": None},
        {**SPEC, "resources": []},
        {**SPEC, "resources": ["post", "post"]},
        {**SPEC, "resources": "post"},
        {**SPEC, "resources": ["*"]},
        {**SPEC, "resources": [None]},
        {**SPEC, "resources": [str(i) for i in range(33)]},
        {**SPEC, "recipient_id": "inferred"},
    ],
)
@pytest.mark.parametrize("dry_run", [False, True])
def test_incomplete_policy_refuses_before_any_write(tmp_path, spec, dry_run):
    with pytest.raises(ValueError, match=r"Shared|Only|literal"):
        AuthPolicyGenerator(tmp_path).generate(
            "assign_category", spec=spec, dry_run=dry_run
        )
    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
async def test_default_policy_remains_the_legacy_deny_all_scaffold(tmp_path):
    generated = _load(tmp_path, spec=None)
    text = (tmp_path / "assign_category_policy.py").read_text()
    assert "@TODO: implement your authorization rules" in text
    assert "AuthProviderProtocol" not in text
    assert not (await generated.AssignCategoryPolicy().evaluate(None, None)).allowed
