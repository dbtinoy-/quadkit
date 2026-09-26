"""Tests for the authorization check mixin (role/permission/ABAC/delegation)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from quadkit.auth.authz.service import AuthorizationService
from quadkit.auth.policies.types import AuthorizationDecision, DecisionOutcome


@dataclass
class User:
    roles: list[str] | str | None = None
    role: str | None = None
    permissions: list[str] | str | None = None
    is_superuser: bool = False
    user_id: str | None = "u1"
    delegations: list[Any] = field(default_factory=list)


@dataclass
class Delegation:
    delegation_id: str = "d1"
    delegator_id: str = "boss"
    permissions: list[str] = field(default_factory=lambda: ["read"])
    resources: list[str] = field(default_factory=list)


def _svc(
    roles: dict[str, Any] | None = None,
    *,
    audit_logger: Any = None,
    max_cache_entries: int = 10000,
) -> AuthorizationService:
    svc = AuthorizationService(
        permission_cache_ttl=0.0,  # force recompute on every check
        max_cache_entries=max_cache_entries,
        audit_logger=audit_logger,
    )
    if roles:
        svc.set_roles(roles)
    return svc


class TestCheckAccessRoles:
    async def test_wildcard_allowed_roles_grants(self) -> None:
        assert await _svc().check_access(None, {"*"}) is True

    async def test_no_user_denies(self) -> None:
        assert await _svc().check_access(None, {"admin"}) is False

    async def test_direct_role_match(self) -> None:
        assert await _svc().check_access(User(roles=["editor"]), {"editor"}) is True
        assert await _svc().check_access(User(roles=["editor"]), {"admin"}) is False

    async def test_single_role_attr(self) -> None:
        assert await _svc().check_access(User(role="viewer"), {"viewer"}) is True

    async def test_admin_bypass(self) -> None:
        assert await _svc().check_access(User(roles=["admin"]), {"whatever"}) is True

    async def test_superuser_bypass(self) -> None:
        assert await _svc().check_access(User(is_superuser=True), {"whatever"}) is True

    async def test_inherited_role_match(self) -> None:
        svc = _svc({"editor": {"permissions": [], "inherits": ["viewer"]}})
        assert await svc.check_access(User(roles=["editor"]), {"viewer"}) is True

    async def test_indirect_inheritance(self) -> None:
        svc = _svc(
            {
                "c": {"inherits": ["b"]},
                "b": {"inherits": ["a"]},
                "a": {},
            }
        )
        assert await svc.check_access(User(roles=["c"]), {"a"}) is True

    async def test_permission_pattern_match(self) -> None:
        svc = _svc({"ops": {"permissions": ["reports.view"]}})
        assert await svc.check_access(User(roles=["ops"]), set(), "reports", "view") is True

    async def test_permission_denied(self) -> None:
        svc = _svc({"ops": {"permissions": ["reports.view"]}})
        assert await svc.check_access(User(roles=["ops"]), set(), "reports", "delete") is False

    async def test_user_direct_permissions_mix_in(self) -> None:
        svc = _svc({"ops": {"permissions": []}})
        user = User(roles=["ops"], permissions=["reports.view"])
        assert await svc.check_access(user, set(), "reports", "view") is True

    async def test_no_resource_no_action_denies(self) -> None:
        svc = _svc({"ops": {"permissions": ["reports.view"]}})
        assert await svc.check_access(User(roles=["ops"]), set()) is False

    async def test_full_resource_string_used_for_permission(self) -> None:
        """Permission matching uses the full ``resource.action`` string."""
        svc = _svc({"ops": {"permissions": ["report:42.view"]}})
        assert await svc.check_access(User(roles=["ops"]), set(), "report:42", "view") is True
        assert await svc.check_access(User(roles=["ops"]), set(), "report:43", "view") is False


class TestPermissionMatching:
    def test_exact_match(self) -> None:
        svc = _svc()
        assert svc._has_permission({"a.b"}, "a.b") is True
        assert svc._has_permission({"a.b"}, "a.c") is False

    def test_global_wildcard(self) -> None:
        svc = _svc()
        assert svc._has_permission({"*"}, "anything.at.all") is True

    def test_user_wildcard_matches_requirement(self) -> None:
        svc = _svc()
        assert svc._has_permission({"admin.*"}, "admin.users") is True
        assert svc._has_permission({"admin.*"}, "users.admin") is False

    def test_requirement_wildcard_matches_user(self) -> None:
        svc = _svc()
        assert svc._has_permission({"community.list"}, "community.*") is True
        assert svc._has_permission({"other.list"}, "community.*") is False

    def test_prefix_suffix_wildcard(self) -> None:
        svc = _svc()
        # multi-* patterns anchor on the first two split parts (prefix+suffix)
        assert svc._has_permission({"a.*.x"}, "a.b.x") is True
        assert svc._has_permission({"a.b.*"}, "a.b.c") is True
        assert svc._has_permission({"a.b.*"}, "a.c.b") is False

    def test_no_false_positive_on_partial(self) -> None:
        svc = _svc()
        assert svc._has_permission({"a.b.c"}, "a.b") is False


class TestFlattenRoles:
    def test_direct_parents(self) -> None:
        svc = _svc({"child": {"inherits": ["parent"]}, "parent": {}})
        assert svc._flatten_roles({"child"}) == {"child", "parent"}

    def test_transitive(self) -> None:
        svc = _svc({"c": {"inherits": ["b"]}, "b": {"inherits": ["a"]}, "a": {}})
        assert svc._flatten_roles({"c"}) == {"c", "b", "a"}

    def test_unknown_roles_pass_through(self) -> None:
        svc = _svc()
        assert svc._flatten_roles({"ghost"}) == {"ghost"}

    def test_inheritance_cycle_is_safe(self) -> None:
        svc = _svc({"a": {"inherits": ["b"]}, "b": {"inherits": ["a"]}})
        assert svc._flatten_roles({"a"}) == {"a", "b"}

    def test_dict_and_attribute_forms(self) -> None:
        @dataclass
        class AttrRole:
            inherits: list[str] = field(default_factory=lambda: ["p2"])

        svc = AuthorizationService()
        svc._roles = {"a": AttrRole(), "b": {"inherits": ["p1"]}}
        assert svc._flatten_roles({"a", "b"}) == {"a", "b", "p1", "p2"}


class TestHasAnyRole:
    def test_object_user(self) -> None:
        svc = _svc({"editor": {"inherits": ["viewer"]}})
        assert svc.has_any_role(User(roles=["editor"]), ["viewer"]) is True

    def test_dict_user(self) -> None:
        svc = _svc()
        assert svc.has_any_role({"roles": ["ops"]}, ["ops"]) is True

    def test_role_attr(self) -> None:
        svc = _svc()
        assert svc.has_any_role(User(role="solo"), ["solo"]) is True

    def test_superuser_bypass(self) -> None:
        assert _svc().has_any_role(User(is_superuser=True), ["admin"]) is True
        assert _svc().has_any_role({"is_superuser": True}, ["admin"]) is True

    def test_no_user(self) -> None:
        assert _svc().has_any_role(None, ["admin"]) is False

    def test_inherited(self) -> None:
        svc = _svc({"manager": {"inherits": ["viewer"]}})
        assert svc.has_any_role(User(roles=["manager"]), ["viewer"]) is True
        assert svc.has_any_role(User(roles=["manager"]), ["editor"]) is False


class TestHasAnyPermission:
    def test_role_permissions(self) -> None:
        svc = _svc({"ops": {"permissions": ["x.view", "y.edit"]}})
        assert svc.has_any_permission(User(roles=["ops"]), ["y.edit"]) is True
        assert svc.has_any_permission(User(roles=["ops"]), ["z.view"]) is False

    def test_user_permission_attr(self) -> None:
        svc = _svc({"ops": {"permissions": []}})
        assert svc.has_any_permission(User(roles=["ops"], permissions=["z.view"]), ["z.view"]) is True

    def test_dict_user(self) -> None:
        svc = _svc()
        assert svc.has_any_permission({"roles": [], "permissions": ["p.q"]}, ["p.q"]) is True

    def test_wildcard_permission(self) -> None:
        svc = _svc({"boss": {"permissions": ["store.*"]}})
        assert svc.has_any_permission(User(roles=["boss"]), ["store.read"]) is True

    def test_no_user(self) -> None:
        assert _svc().has_any_permission(None, ["a.b"]) is False


class TestCanHelpers:
    async def test_can_grants(self) -> None:
        svc = _svc({"ops": {"permissions": ["reports.view"]}})
        assert await svc.can(User(roles=["ops"]), "view", "reports") is True

    async def test_can_denies(self) -> None:
        svc = _svc({"ops": {"permissions": ["reports.view"]}})
        assert await svc.can(User(roles=["ops"]), "delete", "reports") is False

    async def test_can_verbs(self) -> None:
        svc = _svc({"ops": {"permissions": ["r.view", "r.create", "r.update", "r.delete"]}})
        user = User(roles=["ops"])
        assert await svc.can_view(user, "r") is True
        assert await svc.can_create(user, "r") is True
        assert await svc.can_update(user, "r") is True
        assert await svc.can_delete(user, "r") is True

    async def test_can_execute_action(self) -> None:
        svc = _svc({"ops": {"permissions": ["job.run"]}})
        assert await svc.can_execute_action(User(roles=["ops"]), "job", "run") is True
        assert await svc.can_execute_action(User(roles=["ops"]), "job", "stop") is False

    async def test_no_user_false(self) -> None:
        svc = _svc()
        assert await svc.can(None, "view", "r") is False


class TestAuthorize:
    async def test_ok_granted(self) -> None:
        svc = _svc({"ops": {"permissions": ["r.view"]}})
        result = await svc.authorize(User(roles=["ops"]), "view", "r")
        assert result.is_ok()
        assert result.unwrap_or(False) is True

    async def test_ok_denied(self) -> None:
        svc = _svc({"ops": {"permissions": ["r.view"]}})
        result = await svc.authorize(User(roles=["ops"]), "delete", "r")
        assert result.is_ok()
        assert result.unwrap_or(True) is False

    async def test_non_string_resource_coerced(self) -> None:
        svc = _svc({"ops": {"permissions": ["1.view"]}})

        class Res:
            def __str__(self) -> str:
                return "1"

        result = await svc.authorize(User(roles=["ops"]), "view", Res())
        assert result.is_ok()
        assert result.unwrap_or(False) is True

    async def test_audit_logger_receives_decision(self) -> None:
        entries: list[Any] = []

        class _Logger:
            async def log(self, entry: Any) -> None:
                entries.append(entry)

        svc = _svc({"ops": {"permissions": ["r.view"]}}, audit_logger=_Logger())
        await svc.authorize(User(roles=["ops"], user_id="u9"), "view", "r")
        await svc.authorize(User(roles=["ops"], user_id="u9"), "delete", "r")
        assert [e.outcome for e in entries] == ["granted", "denied"]
        assert entries[0].actor_id == "u9"
        assert entries[0].resource_id == "r"
        assert entries[0].metadata["authz_action"] == "view"

    async def test_no_audit_logger_is_fine(self) -> None:
        svc = _svc({"ops": {"permissions": ["r.view"]}})
        result = await svc.authorize(User(roles=["ops"]), "view", "r")
        assert result.is_ok()


class TestPermissionCache:
    async def test_cache_hit_skips_recomputation(self) -> None:
        svc = _svc({"ops": {"permissions": ["a.b"]}})
        svc._permission_cache_ttl = 9999.0
        assert await svc.check_access(User(roles=["ops"]), set(), "a", "b") is True
        assert "u1" in svc._permission_cache
        # second call served from cache (same set object)
        first = svc._permission_cache["u1"][1]
        assert await svc.check_access(User(roles=["ops"]), set(), "a", "b") is True
        assert svc._permission_cache["u1"][1] is first

    async def test_stale_cache_recomputes(self) -> None:
        from quadkit.primitives import clock

        svc = _svc({"ops": {"permissions": ["a.b"]}})
        assert await svc.check_access(User(roles=["ops"]), set(), "a", "b") is True
        expiry = svc._permission_cache["u1"][0]
        # ttl=0: entry expires immediately (expiry <= now), so it is recomputed
        assert expiry <= clock.monotonic()
        assert await svc.check_access(User(roles=["ops"]), set(), "a", "b") is True

    def test_fifo_eviction_at_capacity(self) -> None:
        svc = _svc({"ops": {"permissions": ["a.b"]}}, max_cache_entries=2)

        @dataclass
        class U:
            roles: list[str] = field(default_factory=lambda: ["ops"])
            user_id: str | None = None

        import asyncio

        async def run() -> None:
            for uid in ("a", "b", "c"):
                await svc.check_access(U(user_id=uid), set(), "a", "b")

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(run())
        finally:
            loop.close()
        # "a" evicted first (FIFO), "b" and "c" remain
        assert "a" not in svc._permission_cache
        assert "b" in svc._permission_cache
        assert "c" in svc._permission_cache


class TestDelegations:
    async def test_delegation_grants(self) -> None:
        svc = _svc({"ops": {"permissions": []}})
        user = User(
            roles=["ops"],
            delegations=[Delegation(permissions=["view"], resources=["reports"])],
        )
        assert await svc.check_access(user, set(), "reports", "view") is True

    async def test_delegation_wrong_resource_denies(self) -> None:
        svc = _svc({"ops": {"permissions": []}})
        user = User(
            roles=["ops"],
            delegations=[Delegation(permissions=["view"], resources=["other"])],
        )
        assert await svc.check_access(user, set(), "reports", "view") is False

    async def test_delegation_wildcard_permission(self) -> None:
        svc = _svc({"ops": {"permissions": []}})
        user = User(
            roles=["ops"],
            delegations=[Delegation(permissions=["*"], resources=["reports"])],
        )
        assert await svc.check_access(user, set(), "reports", "delete") is True

    async def test_delegation_requires_resource_match(self) -> None:
        svc = _svc({"ops": {"permissions": []}})
        user = User(
            roles=["ops"],
            delegations=[Delegation(permissions=["view"], resources=["*"])],
        )
        assert await svc.check_access(user, set(), "anything", "view") is True


class TestAbacPolicyEngine:
    async def test_policy_deny_overrides(self) -> None:
        svc = _svc({"ops": {"permissions": ["r.view"]}})
        svc._policy_engine = _Engine(_decision(DecisionOutcome.DENY))
        assert await svc.check_access(User(roles=["ops"]), set(), "r", "view") is False

    async def test_policy_allow_grants_without_permission(self) -> None:
        svc = _svc({"ops": {"permissions": []}})
        svc._policy_engine = _Engine(_decision(DecisionOutcome.ALLOW))
        assert await svc.check_access(User(roles=["ops"]), set(), "r", "view") is True

    async def test_policy_indeterminate_falls_through(self) -> None:
        svc = _svc({"ops": {"permissions": ["r.view"]}})
        svc._policy_engine = _Engine(_decision(DecisionOutcome.INDETERMINATE))
        assert await svc.check_access(User(roles=["ops"]), set(), "r", "view") is True

    async def test_policy_receives_principal(self) -> None:
        svc = _svc({"ops": {"permissions": ["r.view"]}})
        svc._policy_engine = _Engine(_decision(DecisionOutcome.ALLOW))
        await svc.check_access(User(roles=["ops"], user_id="u77"), set(), "r", "view")
        assert svc._policy_engine.last_principals == ["user:u77"]


class _Engine:
    def __init__(self, decision: Any) -> None:
        self._d = decision
        self.last_principals: list[str] = []

    def evaluate(self, req: Any) -> Any:
        self.last_principals.append(req.principal)
        return self._d


def _decision(outcome: DecisionOutcome) -> Any:
    return AuthorizationDecision(decision=outcome)
