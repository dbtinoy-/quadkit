"""Scenario coverage for auth guards and the authentication middleware.

Covers the ``web/guards.py`` surface end-to-end (AuthGuard/RoleGuard/
PermissionGuard fail-closed semantics, CompositeGuard, ``use_guards`` and
the ``require_*`` decorators, ``GuardFactory`` caching) and the pure-ASGI
``AuthMiddleware`` (authentication chain: lockout → token cache → API key →
session → JWT, request-scope user state, 401/403 enforcement, OPTIONS and
excluded-path bypasses, rate-limited login paths) plus the
``AuthResponseHandler`` and the ``require_mfa`` step-up decorator.

Includes the BUG #39 regression guard: ``require_auth``/``require_admin``
built ``GuardContext`` positionally, but ``DomainModel.__init__`` only
binds keyword arguments — positional args were silently dropped, so
authenticated users were rejected with 401.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from quadkit.result import Err, Ok

from quadkit.auth.config import AuthMiddlewareConfig
from quadkit.auth.models.user import User
from quadkit.auth.types import GuardContext
from quadkit.auth.web.guards import (
    AdminGuard,
    AuthGuard,
    CompositeGuard,
    GuardFactory,
    PermissionGuard,
    RoleGuard,
    UserGuard,
    require_admin,
    require_auth,
    require_permission,
    require_role,
    use_guards,
)
from quadkit.auth.web.middleware.auth import (
    AuthMiddleware,
    require_mfa,
)
from quadkit.auth.web.middleware.response_handler import AuthResponseHandler


# --------------------------------------------------------------------------
# Fakes
# --------------------------------------------------------------------------


class _RecordingResponse:
    def __init__(self, status: int, content: Any, headers: dict[str, Any] | None) -> None:
        self.status = status
        self.content = content
        self.headers = headers

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": self.status,
                "headers": [(k.lower().encode(), v.encode()) for k, v in (self.headers or {}).items()],
            }
        )
        await send({"type": "http.response.body", "body": b"{}"})


class _FakeResponseFactory:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def json(
        self,
        content: Any,
        status_code: int = 200,
        headers: dict[str, str] | None = None,
    ) -> _RecordingResponse:
        self.calls.append(("json", {"content": content, "status_code": status_code, "headers": headers}))
        return _RecordingResponse(status_code, content, headers)

    def redirect(self, url: str, status_code: int = 302, headers: dict[str, str] | None = None) -> _RecordingResponse:
        self.calls.append(("redirect", {"url": url, "status_code": status_code}))
        return _RecordingResponse(status_code, {"url": url}, headers)

    def html(
        self,
        content: str,
        status_code: int = 200,
        headers: dict[str, str] | None = None,
    ) -> _RecordingResponse:
        self.calls.append(("html", {"content": content, "status_code": status_code}))
        return _RecordingResponse(status_code, content, headers)


class _FakeResolver:
    """Satisfies ContainerResolverProtocol (all members) for get_resolver().

    ``_global_instance`` doubles as the "global container" fallback that
    ``response_handler._get_response_factory`` uses when no request is
    passed (see ``forbidden_response``).
    """

    _global_instance: "_FakeResolver | None" = None

    def __init__(self, services: dict[Any, Any] | None = None) -> None:
        self._services = services or {}

    async def resolve(self, cls: Any, *, bypass_visibility: bool = False) -> Any:
        if cls not in self._services:
            msg = f"not registered: {cls}"
            raise RuntimeError(msg)
        return self._services[cls]

    async def resolve_optional(self, cls: Any, *, bypass_visibility: bool = False) -> Any:
        return self._services.get(cls)

    async def resolve_all(self, cls: Any, *, bypass_visibility: bool = False) -> Any:
        return [self._services[cls]] if cls in self._services else []

    def has(self, cls: Any, *, bypass_visibility: bool = False) -> bool:
        return cls in self._services

    def resolve_sync(self, cls: Any) -> Any:
        """Synchronously resolve an already-instantiated service.

        ``ContainerResolverProtocol`` carries this member (the container
        implements it for decorators and other sync contexts), and the
        protocol is ``runtime_checkable``: ``get_resolver`` decides by
        ``isinstance``, so a double without it is no longer recognised as a
        resolver at all. The fake holds its services eagerly, so everything
        registered here counts as already instantiated.
        """
        if cls not in self._services:
            from quadkit.contracts.exceptions import UnresolvableDependencyError

            msg = f"Cannot resolve {cls} synchronously: not registered"
            raise UnresolvableDependencyError(msg)
        return self._services[cls]

    async def create_scope(self, *args: Any, **kwargs: Any) -> Any:
        return self

    def bind(self, *args: Any, **kwargs: Any) -> Any:
        return self

    async def call(self, *args: Any, **kwargs: Any) -> Any:
        return None


class _FakeAuthProvider:
    def __init__(self, **overrides: Any) -> None:
        self.roles: dict[str, list[str]] = {}
        self.permissions: dict[str, list[str]] = {}
        self.users: dict[str, User] = {}
        self.api_key_manager = overrides.get("api_key_manager")
        self.session_manager = overrides.get("session_manager")
        self.delegation_manager = None
        self.mfa_manager = overrides.get("mfa_manager")
        self.cache_service = None

    def has_any_role(self, user: User, roles: list[str]) -> bool:
        return any(role in self.roles.get(user.user_id, []) for role in roles)

    def has_any_permission(self, user: User, permissions: list[str]) -> bool:
        return any(p in self.permissions.get(user.user_id, []) for p in permissions)

    async def get_user(self, user_id: str) -> User | None:
        return self.users.get(user_id)


def _request(
    user: User | None = None,
    method: str = "GET",
    path: str = "/api/x",
    resolver: _FakeResolver | None = None,
    cookies: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
    **extra_state: Any,
) -> SimpleNamespace:
    state = SimpleNamespace(user=user)
    for key, value in extra_state.items():
        setattr(state, key, value)
    scope: dict[str, Any] = {"type": "http", "path": path, "method": method}
    if resolver is not None:
        scope["quadkit_resolver"] = resolver
    request = SimpleNamespace(
        state=state,
        headers=headers or {},
        method=method,
        url=SimpleNamespace(path=path),
        cookies=cookies or {},
        scope=scope,
        client=SimpleNamespace(host="10.0.0.1"),
        query_params={},
    )
    # get_resolver() (used by require_mfa / response handlers) finds the
    # resolver via well-known attributes, not the ASGI scope key
    if resolver is not None:
        request.resolver = resolver
    return request


def _asgi_scope(path: str = "/api/x", method: str = "GET", **scope_extra: Any) -> dict[str, Any]:
    scope: dict[str, Any] = {
        "type": "http",
        "path": path,
        "method": method,
        "headers": [],
        "query_string": b"",
        "root_path": "",
        "client": ("127.0.0.1", 12345),
        # Starlette's Request.app property reads scope["app"] when
        # get_resolver() probes ``context.app``
        "app": None,
    }
    scope.update(scope_extra)
    return scope


# --------------------------------------------------------------------------
# Guard unit behavior
# --------------------------------------------------------------------------


async def test_auth_guard_authentication() -> None:
    guard = AuthGuard()
    assert await guard.can_activate(GuardContext(user=User(email="u@x.com"))) is True
    assert await guard.can_activate(GuardContext(user=None)) is False
    # the normalized request-context user id also satisfies authentication
    ctx = GuardContext(user=None, request_context_user_id="u-123")
    assert await guard.can_activate(ctx) is True


async def test_auth_guard_rejection_response() -> None:
    rf = _FakeResponseFactory()
    resolver = _FakeResolver({"quadkit.contracts.web.ResponseFactoryProtocol": rf})
    # the guards resolve by the protocol class itself
    from quadkit.contracts.web import ResponseFactoryProtocol

    from quadkit.di.resolution.context import ContainerResolverProtocol

    assert isinstance(_FakeResolver({}), ContainerResolverProtocol)
    resolver = _FakeResolver({ResponseFactoryProtocol: rf})
    ctx = GuardContext(user=None, request=_request(resolver=resolver))

    response = await AuthGuard().handle_rejection(ctx)
    assert response.status == 401
    assert response.content["error"] == "unauthorized"

    # without a resolver the guard raises (fail closed)
    with pytest.raises(RuntimeError, match="ResponseFactoryProtocol not available"):
        await AuthGuard().handle_rejection(GuardContext(user=None, request=_request()))


async def test_role_guard() -> None:
    user = User(email="u@x.com", roles=["editor"])
    admin_user = User(email="a@x.com", roles=["admin", "editor"])

    guard = RoleGuard("admin", "editor")
    assert await guard.can_activate(GuardContext(user=user)) is True
    assert await guard.can_activate(GuardContext(user=User(email="n@x.com"))) is False
    assert await guard.can_activate(GuardContext(user=None)) is False
    assert await AdminGuard().can_activate(GuardContext(user=admin_user)) is True
    assert await AdminGuard().can_activate(GuardContext(user=user)) is False


async def test_permission_guard_fail_closed_matrix() -> None:
    from quadkit.contracts.auth import AuthProviderProtocol

    provider = _FakeAuthProvider()
    provider.permissions["u1"] = ["read"]
    user = User(email="u@x.com")
    user.user_id = "u1"

    def _ctx(u: User | None) -> GuardContext:
        return GuardContext(
            user=u,
            request=_request(resolver=_FakeResolver({AuthProviderProtocol: provider})),
        )

    all_guard = PermissionGuard("read", "write")
    # all required: one missing -> deny
    assert await all_guard.can_activate(_ctx(user)) is False

    # all present -> allow
    provider.permissions["u1"] = ["read", "write"]
    assert await all_guard.can_activate(_ctx(user)) is True

    # require_all=False: any-of semantics
    any_guard = PermissionGuard("read", "write", require_all=False)
    provider.permissions["u1"] = ["read"]
    assert await any_guard.can_activate(_ctx(user)) is True
    provider.permissions["u1"] = []
    assert await any_guard.can_activate(_ctx(user)) is False

    # no user -> deny; no declared permissions -> fail closed
    assert await all_guard.can_activate(_ctx(None)) is False
    assert await PermissionGuard().can_activate(_ctx(user)) is False

    # no resolver -> deny (fail closed)
    assert (
        await PermissionGuard("read").can_activate(
            GuardContext(user=user, request=_request())
        )
        is False
    )

    # resolver raising -> deny (fail closed)
    class _BrokenResolver:
        async def resolve(self, cls: Any) -> Any:
            msg = "boom"
            raise RuntimeError(msg)

    assert (
        await PermissionGuard("read").can_activate(
            GuardContext(user=user, request=_request(resolver=_BrokenResolver()))
        )
        is False
    )


async def test_composite_guard_and_factory() -> None:
    from quadkit.contracts.web import GuardProtocol  # noqa: F401

    ok = AuthGuard()
    deny = AdminGuard()
    ctx_user = GuardContext(user=User(email="u@x.com"))

    composite = CompositeGuard(ok, deny)
    assert await composite.can_activate(ctx_user) is False
    composite_ok = CompositeGuard(ok, AuthGuard())
    assert await composite_ok.can_activate(ctx_user) is True
    assert await CompositeGuard().can_activate(ctx_user) is True

    # factory caches per guard type
    first = await GuardFactory.get_guard(AuthGuard)
    second = await GuardFactory.get_guard(AuthGuard)
    assert first is second
    # resolver-provided instance wins (documented contract): the cache is
    # only a fallback for types that are not DI-registered — pass the
    # resolver directly (it IS a ContainerResolverProtocol instance)
    GuardFactory._instances.pop("RoleGuard", None)  # noqa: SLF001 — test isolation
    injected = RoleGuard("x")
    got = await GuardFactory.get_guard(RoleGuard, _FakeResolver({RoleGuard: injected}))
    assert got is injected


# --------------------------------------------------------------------------
# Decorators (use_guards / require_*)
# --------------------------------------------------------------------------


def _handler() -> tuple[Any, list[str]]:
    called: list[str] = []

    async def func(request: Any) -> str:
        called.append("ran")
        return "ok"

    return func, called


async def test_use_guards_happy_path_and_rejection() -> None:
    rf = _FakeResponseFactory()
    from quadkit.contracts.web import ResponseFactoryProtocol

    func, called = _handler()
    guarded = use_guards(AuthGuard())(func)
    assert len(guarded.__guards__) == 1

    # authenticated -> handler runs
    user = User(email="u@x.com")
    assert await guarded(_request(user=user)) == "ok"
    assert called == ["ran"]

    # unauthenticated -> 401 rejection response
    called.clear()
    rejected = await guarded(_request(resolver=_FakeResolver({ResponseFactoryProtocol: rf})))
    assert called == []
    assert rejected.status == 401

    # OPTIONS preflight bypasses guards entirely
    called.clear()
    assert await guarded(_request(user=None, method="OPTIONS")) == "ok"

    # request discoverable via keyword argument too
    called.clear()
    assert await guarded(request=_request(user=user)) == "ok"


async def test_use_guards_fails_closed_without_request() -> None:
    func, _ = _handler()
    guarded = use_guards(AuthGuard())(func)

    async def no_request() -> str:
        return "ok"

    bare = use_guards(AuthGuard())(no_request)
    with pytest.raises(ValueError, match="request context"):
        await bare()


async def test_require_auth_regressions() -> None:
    """BUG #39 regression: positional GuardContext dropped the user."""
    rf = _FakeResponseFactory()
    from quadkit.contracts.web import ResponseFactoryProtocol

    user = User(email="u@x.com")
    func, called = _handler()
    guarded = require_auth()(func)

    # authenticated user MUST get through
    assert await guarded(_request(user=user)) == "ok"
    assert called == ["ran"]

    # unauthenticated -> 401
    rejected = await guarded(
        _request(resolver=_FakeResolver({ResponseFactoryProtocol: rf}))
    )
    assert rejected.status == 401

    # OPTIONS bypass
    called.clear()
    assert await guarded(_request(user=None, method="OPTIONS")) == "ok"


async def test_require_admin_and_roles_permissions() -> None:
    from quadkit.contracts.auth import AuthProviderProtocol
    from quadkit.contracts.web import ResponseFactoryProtocol

    rf = _FakeResponseFactory()
    provider = _FakeAuthProvider()
    admin = User(email="a@x.com")
    admin.user_id = "u-admin"
    admin.roles = ["admin"]
    admin.permissions = ["orders:read"]
    provider.roles["u-admin"] = ["admin"]
    provider.permissions["u-admin"] = ["orders:read"]
    resolver = _FakeResolver(
        {ResponseFactoryProtocol: rf, AuthProviderProtocol: provider}
    )

    func, called = _handler()
    guarded_admin = require_admin()(func)
    assert await guarded_admin(_request(user=admin, resolver=resolver)) == "ok"
    assert called == ["ran"]
    assert (await guarded_admin(_request(user=User(email="x@x.com"), resolver=resolver))).status == 403

    guarded_role = require_role("admin")(func)
    assert (await guarded_role(_request(user=User(email="x@x.com"), resolver=resolver))).status == 403

    guarded_perm = require_permission("orders:read")(func)
    assert await guarded_perm(_request(user=admin, resolver=resolver)) == "ok"

    # missing permission -> 403 via the fail-closed permission check
    outsider = User(email="o@x.com")
    outsider.user_id = "u-outsider"
    assert (await guarded_perm(_request(user=outsider, resolver=resolver))).status == 403


# --------------------------------------------------------------------------
# AuthMiddleware: authentication chain
# --------------------------------------------------------------------------


class _FakeApiKeyManager:
    def __init__(self, user: User | None) -> None:
        self._user = user
        self.calls = 0

    async def validate_key(self, key: str, ip_address: str | None = None) -> Any:
        self.calls += 1
        if key == "sk_valid":
            return SimpleNamespace(user_id=self._user.user_id if self._user else None)
        return None


class _FakeSessionManager:
    def __init__(self, user_id: str | None) -> None:
        self._user_id = user_id

    async def validate_session(self, session_id: str) -> Any | None:
        if session_id == "sess-ok" and self._user_id:
            return SimpleNamespace(user_id=self._user_id)
        return None


class _FakeTracker:
    def __init__(self, locked: bool = False) -> None:
        self._locked = locked
        self.locked_calls = 0
        self.failures: list[str] = []

    async def is_locked(self, identifier: str) -> bool:
        self.locked_calls += 1
        return self._locked

    async def record_failure(self, identifier: str) -> None:
        self.failures.append(identifier)


def _make_middleware(
    user: User | None,
    tracker: _FakeTracker | None = None,
    **provider_overrides: Any,
) -> AuthMiddleware:
    provider = _FakeAuthProvider(
        api_key_manager=provider_overrides.pop("api_key_manager", None),
        session_manager=provider_overrides.pop("session_manager", None),
        mfa_manager=provider_overrides.pop("mfa_manager", None),
    )
    if user:
        provider.users[user.user_id] = user
        provider_overrides.setdefault("users", provider.users)
    mw = AuthMiddleware(provider, ctx=None, attempt_tracker=tracker)
    # stub the JWT authenticator to avoid real token verification
    async def fake_jwt_authenticate(request: Any) -> Any:
        return provider_overrides.get("jwt_user")

    mw.jwt_authenticator.authenticate = fake_jwt_authenticate  # type: ignore[method-assign]
    return mw


async def test_authenticate_request_chain() -> None:
    user = User(email="u@x.com")

    # 1. no token -> None, tracker untouched
    mw = _make_middleware(None, tracker=_FakeTracker())
    assert await mw.authenticate_request(_request()) is None
    assert mw.attempt_tracker.locked_calls == 0  # noqa: SLF001

    # 2. locked client -> None before any authenticator runs
    tracker = _FakeTracker(locked=True)
    api = _FakeApiKeyManager(user)
    mw2 = _make_middleware(user, tracker=tracker, api_key_manager=api)
    locked_req = _request(headers={"Authorization": "Bearer sk_valid"})
    assert await mw2.authenticate_request(locked_req) is None
    assert tracker.locked_calls == 1
    assert api.calls == 0

    # 3. API key path: sk_ prefix -> validate -> user, token cached
    api2 = _FakeApiKeyManager(user)
    mw3 = _make_middleware(user, api_key_manager=api2)
    got = await mw3.authenticate_request(_request(headers={"Authorization": "Bearer sk_valid"}))
    assert got is user
    assert api2.calls == 1
    # second call served from the token cache — no second validation
    again = await mw3.authenticate_request(_request(headers={"Authorization": "Bearer sk_valid"}))
    assert again is user
    assert api2.calls == 1

    # 4. session path: cookie session_id -> validate -> user,
    #    session stashed on request.state for downstream use
    sess = _FakeSessionManager(user.user_id)
    mw4 = _make_middleware(user, session_manager=sess)
    req4 = _request(headers={"Authorization": "Bearer not-an-api-key"}, cookies={"session_id": "sess-ok"})
    got4 = await mw4.authenticate_request(req4)
    assert got4 is user
    assert req4.state.session is not None

    # 5. JWT path: authenticator returns a user -> cached
    jwt_user = User(email="j@x.com")
    mw5 = _make_middleware(jwt_user, jwt_user=jwt_user)
    jwt_req = _request(headers={"Authorization": "Bearer jwt.token.here"})
    got5 = await mw5.authenticate_request(jwt_req)
    assert got5 is jwt_user
    cached_jwt = await mw5.authenticate_request(jwt_req)
    assert cached_jwt is jwt_user

    # 6. all authenticators fail -> record_failure called
    tracker2 = _FakeTracker()
    mw6 = _make_middleware(None, tracker=tracker2)
    assert await mw6.authenticate_request(_request(headers={"Authorization": "Bearer sk_bad"})) is None
    assert tracker2.failures == ["10.0.0.1"]


# --------------------------------------------------------------------------
# AuthMiddleware: ASGI __call__
# --------------------------------------------------------------------------


async def _run_middleware(
    mw: AuthMiddleware,
    path: str = "/api/x",
    method: str = "GET",
    app: Any = None,
    **scope_extra: Any,
) -> dict[str, Any]:
    """Drive the middleware over a fake ASGI app; capture the response."""
    messages: list[dict[str, Any]] = []
    scope = _asgi_scope(path=path, method=method, **scope_extra)

    seen_app_called = {"v": False}

    async def inner_app(s: dict[str, Any], receive: Any, send: Any) -> None:
        seen_app_called["v"] = True
        if app is not None:
            await app(s, receive, send)
            return
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", b"application/json")],
            }
        )
        await send({"type": "http.response.body", "body": b'{"ok": true}'})

    # get_resolver() (response handlers) finds the resolver via the
    # request's state attributes, not the ASGI scope — expose it on
    # state for the StarletteRequest the middleware constructs
    if "quadkit_resolver" in scope:
        scope["state"] = {"resolver": scope["quadkit_resolver"]}

    mw.set_app(inner_app)
    resolver_instance = scope.get("quadkit_resolver")

    # AuthResponseHandler.forbidden_response() does not take a request
    # argument, so its module-level _get_response_factory falls back to a
    # global container; expose this fake as that container for the test
    import quadkit.auth.web.middleware.response_handler as _rh

    _orig_global = _FakeResolver._global_instance
    _orig_get_rf = _rh._get_response_factory
    _FakeResolver._global_instance = resolver_instance

    async def _test_get_response_factory(context: Any = None) -> Any:
        rf_inst = _FakeResolver._global_instance
        if rf_inst is None:
            return None
        from quadkit.contracts.web import ResponseFactoryProtocol

        return rf_inst._services.get(ResponseFactoryProtocol)

    _rh._get_response_factory = _test_get_response_factory  # type: ignore[assignment]

    async def receive() -> dict[str, Any]:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: dict[str, Any]) -> None:
        messages.append(message)

    try:
        await mw(scope, receive, send)
    finally:
        _FakeResolver._global_instance = _orig_global
        _rh._get_response_factory = _orig_get_rf  # type: ignore[assignment]
    return {
        "scope": scope,
        "app_called": seen_app_called["v"],
        "status": next((m["status"] for m in messages if m.get("type") == "http.response.start"), None),
        "messages": messages,
    }


async def test_middleware_bypass_paths() -> None:
    user = User(email="u@x.com")
    # excluded path
    mw2 = _make_middleware(user)
    mw2.config.exclude_paths = ["/healthz"]  # type: ignore[misc]
    result2 = await _run_middleware(mw2, path="/healthz")
    assert result2["app_called"] is True

    # OPTIONS preflight
    result3 = await _run_middleware(_make_middleware(None), method="OPTIONS")
    assert result3["app_called"] is True

    # no user + ResponseFactoryProtocol available -> 401 response,
    # app never called
    from quadkit.contracts.web import ResponseFactoryProtocol

    rf = _FakeResponseFactory()
    mw4 = _make_middleware(None)
    result4 = await _run_middleware(
        mw4, quadkit_resolver=_FakeResolver({ResponseFactoryProtocol: rf})
    )
    assert result4["app_called"] is False
    assert result4["status"] == 401
    assert rf.calls and rf.calls[0][0] == "json"


async def test_middleware_enforces_auth() -> None:
    from quadkit.contracts.web import ResponseFactoryProtocol

    rf = _FakeResponseFactory()
    resolver = _FakeResolver({ResponseFactoryProtocol: rf})
    user = User(email="u@x.com")

    # required auth, no user -> 401, app never called
    mw = _make_middleware(user)
    result = await _run_middleware(mw, quadkit_resolver=resolver)
    # authenticate_request found no token on the bare ASGI scope -> None
    assert result["app_called"] is False
    assert result["status"] == 401

    # authenticated request: the middleware itself stores user state
    mw2 = _make_middleware(user)
    seen: dict[str, Any] = {}

    # probe app observes the user state the middleware stores
    async def probe_app(s: dict[str, Any], receive: Any, send: Any) -> None:
        seen["user_id"] = s["state"].get("user_id")
        seen["user"] = s["state"].get("user")
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    # monkeypatch the authenticators so the middleware itself sets state
    async def fake_authenticate(request: Any) -> Any:
        return user

    mw2.authenticate_request = fake_authenticate  # type: ignore[method-assign]
    await _run_middleware(mw2, app=probe_app)
    assert seen["user"] is user
    assert seen["user_id"] == user.user_id


async def test_middleware_optional_auth_and_forbidden() -> None:
    user = User(email="u@x.com")
    # optional_auth=True with no user -> app still runs
    mw = _make_middleware(user)
    mw.config.optional_auth = True  # type: ignore[misc]

    async def fake_authenticate(request: Any) -> Any:
        return None

    mw.authenticate_request = fake_authenticate  # type: ignore[method-assign]
    result = await _run_middleware(mw)
    assert result["app_called"] is True

    # roles_required + user without role -> 403
    from quadkit.contracts.web import ResponseFactoryProtocol

    rf = _FakeResponseFactory()
    mw2 = _make_middleware(user)

    async def fake_auth2(request: Any) -> Any:
        return user

    mw2.authenticate_request = fake_auth2  # type: ignore[method-assign]
    # check_authorization delegates to the session validator's provider
    mw2.session_validator.auth_provider = _FakeAuthProvider()
    mw2.config.roles_required = ["admin"]  # type: ignore[misc]
    result = await _run_middleware(
        mw2, quadkit_resolver=_FakeResolver({ResponseFactoryProtocol: rf})
    )
    assert result["status"] == 403


async def test_middleware_rate_limited_login_path() -> None:
    user = User(email="u@x.com")
    mw = _make_middleware(user)

    calls = {"limiter": 0}
    original_limiter = mw.rate_limiter

    class _RecordingLimiter:
        def __init__(self, inner: Any) -> None:
            self.inner = inner
            self.app = None

        async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
            calls["limiter"] += 1
            # the middleware sets ``limiter.app = next_app`` before calling;
            # delegate through it (the real RateLimitMiddleware does too)
            await self.app(scope, receive, send)

    recorder = _RecordingLimiter(original_limiter)
    mw.rate_limiter = recorder  # type: ignore[assignment]

    async def fake_authenticate(request: Any) -> Any:
        return user

    mw.authenticate_request = fake_authenticate  # type: ignore[method-assign]
    result = await _run_middleware(mw, path="/auth/login")
    assert calls["limiter"] == 1
    assert result["app_called"] is True
    del recorder


# --------------------------------------------------------------------------
# AuthResponseHandler
# --------------------------------------------------------------------------


async def test_response_handler() -> None:
    rf = _FakeResponseFactory()

    resp = await AuthResponseHandler.unauthorized_response("nope", response_factory=rf)
    assert resp.status == 401
    assert "WWW-Authenticate" in (rf.calls[0][1]["headers"] or {})

    forbidden = await AuthResponseHandler.forbidden_response("nope", response_factory=rf)
    assert forbidden.status == 403

    # HTML accept + request -> redirect to login with next=
    html_request = _request(headers={"Accept": "text/html"})
    html_request.login_url = "/login"
    redirect_resp = await AuthResponseHandler.unauthorized_response("nope", request=html_request, response_factory=rf)
    assert redirect_resp.status == 302
    assert rf.calls[-1][0] == "redirect"
    assert "/login?next=/api/x" in rf.calls[-1][1]["url"]

    # without a factory the handler raises
    with pytest.raises(RuntimeError, match="ResponseFactoryProtocol not available"):
        await AuthResponseHandler.unauthorized_response("nope")


# --------------------------------------------------------------------------
# require_mfa step-up decorator
# --------------------------------------------------------------------------


class _FakeMFA:
    def __init__(self, enabled: bool) -> None:
        self.is_enabled = enabled


class _FakeMFAManager:
    def __init__(self, mfa: _FakeMFA | None) -> None:
        self._mfa = mfa

    async def get_mfa(self, user_id: str) -> Any:
        return self._mfa


async def test_require_mfa_step_up() -> None:
    from quadkit.contracts.auth import AuthProviderProtocol
    from quadkit.contracts.web import ResponseFactoryProtocol

    rf = _FakeResponseFactory()
    user = User(email="u@x.com")

    def _resolver(provider: _FakeAuthProvider) -> _FakeResolver:
        return _FakeResolver(
            {ResponseFactoryProtocol: rf, AuthProviderProtocol: provider}
        )

    func, called = _handler()
    guarded = require_mfa(max_age_seconds=300)(func)

    # no user -> 401
    resp = await guarded(_request(resolver=_resolver(_FakeAuthProvider())))
    assert resp.status == 401

    # user without MFA enabled -> 403
    provider_off = _FakeAuthProvider(mfa_manager=_FakeMFAManager(_FakeMFA(False)))
    resp_off = await guarded(_request(user=user, resolver=_resolver(provider_off)))
    assert resp_off.status == 403

    # MFA enabled but no step-up session -> 401 step-up
    provider_on = _FakeAuthProvider(mfa_manager=_FakeMFAManager(_FakeMFA(True)))
    resp_nover = await guarded(_request(user=user, resolver=_resolver(provider_on)))
    assert resp_nover.status == 401
    assert resp_nover.content["error"] == "mfa_verification_required"

    # fresh step-up verification -> passes
    fresh = datetime.now(UTC) - timedelta(seconds=30)
    session = SimpleNamespace(mfa_verified_at=fresh)
    resp_ok = await guarded(
        _request(user=user, resolver=_resolver(provider_on), session=session)
    )
    assert resp_ok == "ok"
    assert called == ["ran"]

    # stale step-up verification -> 401 again
    stale = datetime.now(UTC) - timedelta(seconds=400)
    stale_session = SimpleNamespace(mfa_verified_at=stale)
    resp_stale = await guarded(
        _request(user=user, resolver=_resolver(provider_on), session=stale_session)
    )
    assert resp_stale.status == 401

    # no MFA manager at all -> passes through
    provider_none = _FakeAuthProvider()
    assert await guarded(_request(user=user, resolver=_resolver(provider_none))) == "ok"
