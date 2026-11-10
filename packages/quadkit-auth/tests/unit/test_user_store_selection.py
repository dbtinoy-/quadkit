"""User-store selection: forwarding, deferred SQL, honest failure.

The chain under test is
``AuthModule.configure -> AuthBundleProvider -> AuthenticationProvider``:
documented kwargs must not be dropped, a ``"sql"`` selection must build
the SQL store over the root resolver (at boot when the database module
is visible, otherwise on first use — module visibility can hide the
database module's exports during provider boot), and requesting SQL
without a database must fail loudly — never fall back to ephemeral
users silently.
"""

from __future__ import annotations

from typing import Any

import pytest

from quadkit.auth.authn.security import PasswordPolicy
from quadkit.auth.config import AuthConfig, JWTConfig
from quadkit.auth.di.bundle_provider import AuthBundleProvider
from quadkit.auth.di.sub_providers.authentication_provider import (
    AuthenticationProvider,
)
from quadkit.auth.module import AuthModule
from quadkit.auth.storage._deferred_store import DeferredUserStore
from quadkit.auth.storage._sql_store import SQLUserStore
from quadkit.auth.storage.token_store import InMemoryUserStore
from quadkit.contracts import DatabaseProviderProtocol
from quadkit.contracts.core import HealthStatus
from quadkit.contracts.exceptions import ConfigurationError
from quadkit.sql.providers.sqlite_provider import SQLiteProvider

SECRET = "test-secret-key-for-testing-only"  # noqa: S105


def _config(**overrides: Any) -> AuthConfig:
    return AuthConfig(
        secret_key=SECRET,
        token=JWTConfig(secret_key=SECRET),
        **overrides,
    )


class _BootContainer:
    """Minimal resolver: hands back the database, nothing else.

    ``db`` is settable so a test can model module visibility: the
    binding is invisible during boot and resolvable later.
    """

    def __init__(self, db_provider: Any = None) -> None:
        self.db = db_provider

    async def resolve_optional(self, contract: type) -> Any:
        if contract is DatabaseProviderProtocol:
            return self.db
        return None


def test_module_configure_forwards_selection() -> None:
    module = AuthModule.configure(user_store="sql", user_table="app_users")
    bundle = module.providers[0]
    assert isinstance(bundle, AuthBundleProvider)
    assert bundle._authn_kwargs == {
        "user_store_kind": "sql",
        "user_table": "app_users",
    }
    bundle._compose_sub_providers()
    assert isinstance(bundle._authn.user_store, DeferredUserStore)
    assert bundle._authn._user_table == "app_users"


def test_bundle_kwargs_reach_authentication_provider() -> None:
    """Regression: **kwargs were documented as forwarded, then dropped."""
    policy = PasswordPolicy(min_length=12)
    bundle = AuthBundleProvider(config=_config(), password_policy=policy)
    assert bundle._authn.password_policy is policy


def test_config_field_selects_sql() -> None:
    provider = AuthenticationProvider(config=_config(user_store="sql"))
    assert isinstance(provider.user_store, DeferredUserStore)
    assert provider._deferred_sql_store is provider.user_store
    assert provider._user_table == "users"


def test_explicit_store_instance_wins() -> None:
    store = InMemoryUserStore()
    provider = AuthenticationProvider(
        config=_config(), user_store=store, user_store_kind="sql"
    )
    assert provider.user_store is store
    assert provider._deferred_sql_store is None
    assert provider._user_store_kind == "explicit"


@pytest.mark.asyncio
async def test_sql_store_builds_at_boot_not_at_register() -> None:
    db = SQLiteProvider(":memory:")
    await db.connect()
    try:
        provider = AuthenticationProvider(
            config=_config(), user_store_kind="sql", user_table="app_users"
        )
        # Registration-time state: no DB touched yet, health is honest.
        assert isinstance(provider.user_store, DeferredUserStore)
        assert provider._deferred_sql_store.resolved_store is None
        health = await provider.health_check()
        assert health.status is HealthStatus.DEGRADED

        await provider.boot(_BootContainer(db))  # type: ignore[arg-type]

        resolved = provider._deferred_sql_store.resolved_store
        assert isinstance(resolved, SQLUserStore)
        assert resolved.initialized
        assert resolved.table_name == "app_users"
        # One stable store object: the service holds the same deferred
        # store the provider exposes — no post-boot swapping.
        assert provider.service.user_store is provider.user_store
        health = await provider.health_check()
        assert health.status is HealthStatus.HEALTHY

        created = await provider.user_store.create_user(
            name="Ada", email="ada@example.com", hashed_password="h"
        )
        found = await provider.user_store.get_user_by_email("ada@example.com")
        assert found is not None
        assert found.user_id == created.user_id
        assert await db.table_exists("app_users")
    finally:
        await db.disconnect()


@pytest.mark.asyncio
async def test_sql_store_resolves_on_first_use_when_invisible_at_boot() -> None:
    """Module visibility hides DatabaseProviderProtocol during boot in
    a composed app (the database module is not global and the auth
    module does not import it). Boot must defer — loudly reported, not
    failed — and the first identity call, running in the caller's
    unrestricted context, materialises the store."""
    db = SQLiteProvider(":memory:")
    await db.connect()
    try:
        container = _BootContainer(None)  # invisible during boot
        provider = AuthenticationProvider(config=_config(), user_store_kind="sql")
        await provider.boot(container)  # type: ignore[arg-type]
        assert provider._deferred_sql_store.resolved_store is None
        health = await provider.health_check()
        assert health.status is HealthStatus.DEGRADED

        container.db = db  # visible from the caller's context now
        created = await provider.user_store.create_user(
            name="Bo", email="bo@example.com", hashed_password="h"
        )
        assert isinstance(
            provider._deferred_sql_store.resolved_store, SQLUserStore
        )
        found = await provider.user_store.get_user_by_email("bo@example.com")
        assert found is not None
        assert found.user_id == created.user_id
        health = await provider.health_check()
        assert health.status is HealthStatus.HEALTHY
    finally:
        await db.disconnect()


@pytest.mark.asyncio
async def test_sql_without_database_fails_loudly() -> None:
    provider = AuthenticationProvider(config=_config(), user_store_kind="sql")
    await provider.boot(_BootContainer(None))  # type: ignore[arg-type]
    # Deferral is reported, not hidden — and the first use fails loudly
    # rather than falling back to ephemeral users.
    health = await provider.health_check()
    assert health.status is HealthStatus.DEGRADED
    with pytest.raises(ConfigurationError, match="user_store='sql'"):
        await provider.user_store.count_users()
