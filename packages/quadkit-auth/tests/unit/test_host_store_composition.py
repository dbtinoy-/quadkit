"""Host-supplied stores must survive eager and deferred bundle composition."""

from __future__ import annotations

import pytest

from quadkit.auth.config import AuthConfig, JWTConfig
from quadkit.auth.di.bundle_provider import AuthBundleProvider
from quadkit.auth.module import AuthModule
from quadkit.auth.storage.token_store import InMemoryUserStore


@pytest.mark.parametrize("deferred", [False, True])
def test_store_reaches_authentication_service(deferred: bool) -> None:
    store = InMemoryUserStore()
    key = "host-composition-test-secret-at-least-32-characters"
    config = AuthConfig(secret_key=key, token=JWTConfig(secret_key=key))
    module = AuthModule.configure(None if deferred else config, user_store=store)
    bundle = module.providers[0]
    assert isinstance(bundle, AuthBundleProvider)
    if deferred:
        bundle._config = config
        bundle._compose_sub_providers()
    assert bundle._authn.user_store is store
    assert bundle._authn.service.user_store is store
    bundle._compose_sub_providers()
    assert bundle._authn.service.user_store is store


def test_bundle_does_not_silently_discard_invalid_options() -> None:
    key = "host-composition-test-secret-at-least-32-characters"
    config = AuthConfig(secret_key=key, token=JWTConfig(secret_key=key))
    with pytest.raises(TypeError, match="unexpected keyword"):
        AuthBundleProvider(config, unknown_store_option=object())


@pytest.mark.parametrize("deferred", [False, True])
def test_explicit_blacklist_backend_survives_composition(deferred: bool) -> None:
    backend = object()
    key = "host-composition-test-secret-at-least-32-characters"
    config = AuthConfig(secret_key=key, token=JWTConfig(secret_key=key))
    module = AuthModule.configure(None if deferred else config, cache_service=backend)
    bundle = module.providers[0]
    if deferred:
        bundle._config = config
        bundle._compose_sub_providers()
    assert bundle._token._cache_service is backend
    assert bundle._authn.service.token_manager._blacklist_mgr._cache is backend
    bundle._compose_sub_providers()
    assert bundle._token._cache_service is backend
    assert bundle._authn.service.token_manager._blacklist_mgr._cache is backend


@pytest.mark.parametrize("deferred", [False, True])
def test_explicit_session_store_survives_bundle_recomposition(deferred):
    from quadkit.auth.storage.in_memory_stores import InMemorySessionStore

    store = InMemorySessionStore()
    key = "host-composition-test-secret-at-least-32-characters"
    config = AuthConfig(secret_key=key, token=JWTConfig(secret_key=key))
    bundle = AuthModule.configure(
        None if deferred else config, session_store=store
    ).providers[0]
    if deferred:
        bundle._config = config
        bundle._compose_sub_providers()
    assert bundle._session._session_store is store
    bundle._compose_sub_providers()
    assert bundle._session._session_store is store


def test_invalid_explicit_session_store_fails_during_composition():
    key = "host-composition-test-secret-at-least-32-characters"
    config = AuthConfig(secret_key=key, token=JWTConfig(secret_key=key))
    with pytest.raises(TypeError, match="SessionStore"):
        AuthModule.configure(config, session_store=object())
