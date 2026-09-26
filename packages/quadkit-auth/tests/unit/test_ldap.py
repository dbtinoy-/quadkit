"""Tests for the LDAP manager: provider, auth flows, pooling, group checks."""

from __future__ import annotations

import importlib
import sys
import types
from types import SimpleNamespace
from typing import Any

import pytest

import quadkit.auth.authn._ldap_directory as ldap_dir_mod
import quadkit.auth.authn.ldap as ldap_mod
from quadkit.auth.exceptions import AuthError
from quadkit.validation import SecretStr

FAKE_MODULES = ("ldap3", "ldap3.core", "ldap3.core.exceptions")


class _State:
    def __init__(self) -> None:
        self.routes: dict[tuple[str, str], list[Any]] = {}
        self.bind_fail_for: set[str] = set()
        self.conns: list[Any] = []
        self.servers: list[Any] = []


STATE = _State()


class _FakeAttr:
    def __init__(self, value: Any, values: list[Any] | None = None) -> None:
        self.value = value
        self.values = values if values is not None else ([value] if not isinstance(value, list) else value)


def _entry(**attrs: Any) -> Any:
    e = SimpleNamespace()
    for key, val in attrs.items():
        setattr(e, key, val if isinstance(val, _FakeAttr) else _FakeAttr(val))
    return e


class LDAPException(Exception):  # noqa: N818
    """Fake ldap3 exception."""


class Server:
    def __init__(self, url: str, get_info: Any = None) -> None:
        self.url = url
        STATE.servers.append(self)


class Connection:
    def __init__(
        self,
        server: Server,
        user: str | None = None,
        password: str | None = None,
        auto_bind: bool = True,
        read_only: bool = True,
        receive_timeout: int | None = None,
    ) -> None:
        if user in STATE.bind_fail_for:
            raise LDAPException("invalid credentials")
        STATE.conns.append(self)
        self.server = server
        self.user = user
        self.password = password
        self.receive_timeout = receive_timeout
        self.bound = True
        self.entries: list[Any] = []
        self.unbound = False

    def search(
        self,
        search_base: str | None = None,
        search_filter: str | None = None,
        search_scope: Any = None,
        attributes: list[str] | None = None,
    ) -> None:
        for (base, prefix), entries in STATE.routes.items():
            if base == search_base and (prefix is None or search_filter == prefix):
                self.entries = entries
                return
        self.entries = []

    def unbind(self) -> None:
        self.bound = False
        self.unbound = True


def _build_fakes() -> dict[str, Any]:
    fake_ldap3 = types.ModuleType("ldap3")
    fake_ldap3.ALL = "ALL"
    fake_ldap3.BASE = "BASE"
    fake_ldap3.SUBTREE = "SUBTREE"
    fake_ldap3.Server = Server
    fake_ldap3.Connection = Connection
    fake_core = types.ModuleType("ldap3.core")
    fake_exc = types.ModuleType("ldap3.core.exceptions")
    fake_exc.LDAPException = LDAPException
    fake_core.exceptions = fake_exc
    fake_ldap3.core = fake_core

    return {
        "ldap3": fake_ldap3,
        "ldap3.core": fake_core,
        "ldap3.core.exceptions": fake_exc,
    }


@pytest.fixture
def faked_ldap() -> dict[str, Any]:
    saved = {name: sys.modules.get(name) for name in FAKE_MODULES}
    STATE.__init__()
    fakes = _build_fakes()
    for name in FAKE_MODULES:
        sys.modules[name] = fakes[name]
    importlib.reload(ldap_dir_mod)
    importlib.reload(ldap_mod)
    try:
        yield fakes
    finally:
        for name, mod in saved.items():
            if mod is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = mod
        importlib.reload(ldap_mod)
        importlib.reload(ldap_dir_mod)


def _admin_config(**overrides: Any) -> SimpleNamespace:
    base: dict[str, Any] = {
        "name": "ad",
        "server_url": "ldap://ad.local",
        "bind_dn": "CN=svc,DC=local",
        "bind_password": SecretStr("s3cret"),
        "user_search_base": "OU=Users,DC=local",
        "user_search_filter": "(sAMAccountName={username})",
        "user_dn_attribute": "distinguishedName",
        "group_search_base": "OU=Groups,DC=local",
        "group_search_filter": "(cn={group})",
        "require_group_membership": None,
        "tls_ca_cert_file": None,
        "tls_cert_file": None,
        "tls_key_file": None,
        "timeout": 30,
        "max_connections": 10,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _manager(fakes: dict[str, Any], **provider_overrides: Any) -> Any:
    return ldap_mod.LDAPManager({"ad": _admin_config(**provider_overrides)})


USER_DN = "CN=ada,DC=local"
GROUP_DN = "CN=admins,DC=local"


class TestWithoutLibrary:
    def test_missing_library_raises_import_error(self) -> None:
        if ldap_mod.LDAP_AVAILABLE:
            pytest.skip("ldap3 installed; ImportError path not reachable")
        with pytest.raises(ImportError, match="ldap3"):
            ldap_mod.LDAPManager(providers={})


class TestProviderDataclass:
    def test_defaults(self) -> None:
        p = ldap_mod.LDAPProvider(name="ad", server_url="ldap://x")
        assert p.user_search_filter == "(sAMAccountName={username})"
        assert p.user_dn_attribute == "distinguishedName"
        assert p.timeout == 30
        assert p.max_connections == 10
        assert p.bind_dn is None
        assert p.require_group_membership is None


class TestManagerInit:
    def test_converts_admin_config(self, faked_ldap: dict[str, Any]) -> None:
        mgr = _manager(faked_ldap)
        p = mgr.providers["ad"]
        assert isinstance(p, ldap_mod.LDAPProvider)
        assert p.server_url == "ldap://ad.local"
        assert p.timeout == 30

    def test_repr(self, faked_ldap: dict[str, Any]) -> None:
        mgr = _manager(faked_ldap)
        assert "ad" in repr(mgr)


class TestAuthenticateUser:
    async def test_unknown_provider_raises(self, faked_ldap: dict[str, Any]) -> None:
        mgr = _manager(faked_ldap)
        with pytest.raises(AuthError, match="not found"):
            await mgr.authenticate_user("nope", "ada", "pw")

    async def test_user_not_found_returns_none(self, faked_ldap: dict[str, Any]) -> None:
        mgr = _manager(faked_ldap)
        info = await mgr.authenticate_user("ad", "ghost", "pw")
        assert info is None

    async def test_success(self, faked_ldap: dict[str, Any]) -> None:
        mgr = _manager(faked_ldap)
        STATE.routes[("OU=Users,DC=local", "(sAMAccountName=ada)")] = [
            _entry(distinguishedName=USER_DN)
        ]
        STATE.routes[(USER_DN, "(objectClass=*)")] = [
            _entry(
                sAMAccountName="ada",
                mail="ada@example.com",
                displayName="Ada",
                givenName=b"Ada",
            )
        ]
        info = await mgr.authenticate_user("ad", "ada", "pw")
        assert info is not None
        assert info["sAMAccountName"] == "ada"
        assert info["mail"] == "ada@example.com"
        assert info["givenName"] == "Ada"  # bytes decoded

    async def test_bad_password_returns_none(self, faked_ldap: dict[str, Any]) -> None:
        mgr = _manager(faked_ldap)
        STATE.routes[("OU=Users,DC=local", "(sAMAccountName=ada)")] = [
            _entry(distinguishedName=USER_DN)
        ]
        STATE.bind_fail_for.add(USER_DN)
        assert await mgr.authenticate_user("ad", "ada", "wrong") is None

    async def test_ldap_error_wrapped(self, faked_ldap: dict[str, Any]) -> None:
        mgr = _manager(faked_ldap)

        class RaisingSearch:
            def search(self, **kw: Any) -> None:
                raise LDAPException("server down")

        import quadkit.auth.authn._ldap_directory as dm

        real_get = dm._LDAPDirectoryMixin._get_connection

        async def fake_get(self: Any, provider: Any) -> Any:
            conn = await real_get(self, provider)
            conn.search = RaisingSearch().search
            return conn

        dm._LDAPDirectoryMixin._get_connection = fake_get
        try:
            with pytest.raises(AuthError, match="LDAP authentication failed"):
                await mgr.authenticate_user("ad", "ada", "pw")
        finally:
            dm._LDAPDirectoryMixin._get_connection = real_get

    async def test_group_membership_required(self, faked_ldap: dict[str, Any]) -> None:
        mgr = _manager(faked_ldap, require_group_membership="admins")
        STATE.routes[("OU=Users,DC=local", "(sAMAccountName=ada)")] = [
            _entry(distinguishedName=USER_DN)
        ]
        STATE.routes[(USER_DN, "(objectClass=*)")] = [_entry(sAMAccountName="ada")]
        STATE.routes[("OU=Groups,DC=local", "(cn=admins)")] = [_entry(distinguishedName=GROUP_DN)]
        # group entry has no member attribute; user has no memberOf either
        STATE.routes[(GROUP_DN, "(objectClass=*)")] = [_entry(objectClass="group")]
        assert await mgr.authenticate_user("ad", "ada", "pw") is None

    async def test_group_membership_ok(self, faked_ldap: dict[str, Any]) -> None:
        mgr = _manager(faked_ldap, require_group_membership="admins")
        STATE.routes[("OU=Users,DC=local", "(sAMAccountName=ada)")] = [
            _entry(distinguishedName=USER_DN)
        ]
        STATE.routes[(USER_DN, "(objectClass=*)")] = [_entry(sAMAccountName="ada")]
        STATE.routes[("OU=Groups,DC=local", "(cn=admins)")] = [_entry(distinguishedName=GROUP_DN)]
        STATE.routes[(GROUP_DN, "(objectClass=*)")] = [
            _entry(member=_FakeAttr([], values=[USER_DN]))
        ]
        info = await mgr.authenticate_user("ad", "ada", "pw")
        assert info is not None
        assert info["sAMAccountName"] == "ada"


class TestGetUserInfo:
    async def test_unknown_provider_raises(self, faked_ldap: dict[str, Any]) -> None:
        mgr = _manager(faked_ldap)
        with pytest.raises(AuthError, match="not found"):
            await mgr.get_user_info("nope", "ada")

    async def test_found(self, faked_ldap: dict[str, Any]) -> None:
        mgr = _manager(faked_ldap)
        STATE.routes[("OU=Users,DC=local", "(sAMAccountName=ada)")] = [
            _entry(distinguishedName=USER_DN)
        ]
        STATE.routes[(USER_DN, "(objectClass=*)")] = [_entry(mail="ada@example.com")]
        info = await mgr.get_user_info("ad", "ada")
        assert info == {"mail": "ada@example.com"}

    async def test_not_found_returns_none(self, faked_ldap: dict[str, Any]) -> None:
        mgr = _manager(faked_ldap)
        assert await mgr.get_user_info("ad", "ghost") is None

    async def test_error_returns_none(self, faked_ldap: dict[str, Any]) -> None:
        mgr = _manager(faked_ldap)
        exc = LDAPException
        import quadkit.auth.authn._ldap_directory as dm

        class RaisingSearch:
            def search(self, **kw: Any) -> None:
                raise exc("down")

        real_get = dm._LDAPDirectoryMixin._get_connection

        async def fake_get(self: Any, provider: Any) -> Any:
            conn = await real_get(self, provider)
            conn.search = RaisingSearch().search
            return conn

        dm._LDAPDirectoryMixin._get_connection = fake_get
        try:
            assert await mgr.get_user_info("ad", "ada") is None
        finally:
            dm._LDAPDirectoryMixin._get_connection = real_get


class TestGroupMembership:
    async def test_unknown_provider_raises(self, faked_ldap: dict[str, Any]) -> None:
        mgr = _manager(faked_ldap)
        with pytest.raises(AuthError, match="not found"):
            await mgr.check_group_membership("nope", "ada", "admins")

    async def test_member_list_match(self, faked_ldap: dict[str, Any]) -> None:
        mgr = _manager(faked_ldap)
        STATE.routes[("OU=Users,DC=local", "(sAMAccountName=ada)")] = [
            _entry(distinguishedName=USER_DN)
        ]
        STATE.routes[("OU=Groups,DC=local", "(cn=admins)")] = [_entry(distinguishedName=GROUP_DN)]
        STATE.routes[(GROUP_DN, "(objectClass=*)")] = [
            _entry(member=_FakeAttr([], values=[USER_DN]))
        ]
        assert await mgr.check_group_membership("ad", "ada", "admins") is True

    async def test_member_of_match(self, faked_ldap: dict[str, Any]) -> None:
        mgr = _manager(faked_ldap)
        STATE.routes[("OU=Users,DC=local", "(sAMAccountName=ada)")] = [
            _entry(distinguishedName=USER_DN)
        ]
        STATE.routes[("OU=Groups,DC=local", "(cn=admins)")] = [_entry(distinguishedName=GROUP_DN)]
        STATE.routes[(GROUP_DN, "(objectClass=*)")] = [_entry(objectClass="group")]
        STATE.routes[(USER_DN, "(objectClass=*)")] = [
            _entry(memberOf=_FakeAttr([], values=[GROUP_DN]))
        ]
        assert await mgr.check_group_membership("ad", "ada", "admins") is True

    async def test_not_a_member(self, faked_ldap: dict[str, Any]) -> None:
        mgr = _manager(faked_ldap)
        STATE.routes[("OU=Users,DC=local", "(sAMAccountName=ada)")] = [
            _entry(distinguishedName=USER_DN)
        ]
        STATE.routes[("OU=Groups,DC=local", "(cn=admins)")] = [_entry(distinguishedName=GROUP_DN)]
        STATE.routes[(GROUP_DN, "(objectClass=*)")] = [
            _entry(member=_FakeAttr([], values=["CN=other,DC=local"]))
        ]
        STATE.routes[(USER_DN, "(objectClass=*)")] = [_entry()]
        assert await mgr.check_group_membership("ad", "ada", "admins") is False

    async def test_no_group_config_returns_false(self, faked_ldap: dict[str, Any]) -> None:
        mgr = _manager(faked_ldap, group_search_base=None)
        STATE.routes[("OU=Users,DC=local", "(sAMAccountName=ada)")] = [
            _entry(distinguishedName=USER_DN)
        ]
        assert await mgr.check_group_membership("ad", "ada", "admins") is False

    async def test_error_returns_false(self, faked_ldap: dict[str, Any]) -> None:
        mgr = _manager(faked_ldap)
        exc = LDAPException
        import quadkit.auth.authn._ldap_directory as dm

        class RaisingSearch:
            def search(self, **kw: Any) -> None:
                raise exc("down")

        real_get = dm._LDAPDirectoryMixin._get_connection

        async def fake_get(self: Any, provider: Any) -> Any:
            conn = await real_get(self, provider)
            conn.search = RaisingSearch().search
            return conn

        dm._LDAPDirectoryMixin._get_connection = fake_get
        try:
            assert await mgr.check_group_membership("ad", "ada", "admins") is False
        finally:
            dm._LDAPDirectoryMixin._get_connection = real_get


class TestConnectionPool:
    async def test_reuses_bound_connection(self, faked_ldap: dict[str, Any]) -> None:
        mgr = _manager(faked_ldap)
        STATE.routes[("OU=Users,DC=local", "(sAMAccountName=ada)")] = [
            _entry(distinguishedName=USER_DN)
        ]
        await mgr.get_user_info("ad", "ada")
        first = STATE.conns[-1]
        assert len(STATE.conns) == 1
        await mgr.get_user_info("ad", "ada")
        assert len(STATE.conns) == 1  # reused, not recreated
        assert first.bound is True

    async def test_unbound_connection_dropped(self, faked_ldap: dict[str, Any]) -> None:
        mgr = _manager(faked_ldap)
        STATE.routes[("OU=Users,DC=local", "(sAMAccountName=ada)")] = [
            _entry(distinguishedName=USER_DN)
        ]
        await mgr.get_user_info("ad", "ada")
        STATE.conns[-1].bound = False  # simulate disconnect
        await mgr.get_user_info("ad", "ada")
        assert len(STATE.conns) == 2  # a new connection was created

    async def test_pool_overflow_unbinds(self, faked_ldap: dict[str, Any]) -> None:
        mgr = _manager(faked_ldap, max_connections=1)
        STATE.routes[("OU=Users,DC=local", "(sAMAccountName=ada)")] = [
            _entry(distinguishedName=USER_DN)
        ]
        await mgr.get_user_info("ad", "ada")  # conn1 pooled
        await mgr.get_user_info("ad", "ada")  # reuse conn1
        # force pool full: add a dummy conn, then return conn1
        mgr._connection_pool["ad"].append(STATE.conns[0])
        conn = await mgr._get_connection(mgr.providers["ad"])
        mgr._return_connection(mgr.providers["ad"], conn)
        # pool was full (2 > max 1) -> conn unbound
        assert conn.unbound is True

    async def test_bind_password_unwrapped(self, faked_ldap: dict[str, Any]) -> None:
        mgr = _manager(faked_ldap)
        STATE.routes[("OU=Users,DC=local", "(sAMAccountName=ada)")] = [
            _entry(distinguishedName=USER_DN)
        ]
        await mgr.get_user_info("ad", "ada")
        assert STATE.conns[0].password == "s3cret"
        assert STATE.conns[0].user == "CN=svc,DC=local"
