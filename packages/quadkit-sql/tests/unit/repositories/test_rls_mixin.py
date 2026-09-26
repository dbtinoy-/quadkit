"""Tests for the row-level security mixin (_RLSMixin) on a host double."""

from __future__ import annotations

import pytest

from quadkit.sql.repositories._rls_mixin import _RLSMixin
from quadkit.sql.row_level_security import (
    NoSecurityPolicyError,
    RowLevelSecurityPolicy,
    ScopeColumn,
)


class _Host(_RLSMixin):
    def __init__(self, policy: RowLevelSecurityPolicy | None = None) -> None:
        self._rls_policy = policy
        self.table_name = "pets"


def _policy() -> RowLevelSecurityPolicy:
    return RowLevelSecurityPolicy(columns=[ScopeColumn("user_id")])


class TestRLSApply:
    def test_no_policy_returns_unchanged(self) -> None:
        host = _Host(None)
        query, params = host._rls_apply("SELECT * FROM pets", [], "SELECT")
        assert query == "SELECT * FROM pets"
        assert params == []

    def test_no_scope_active_raises(self) -> None:
        host = _Host(_policy())
        with pytest.raises(NoSecurityPolicyError):
            host._rls_apply("SELECT * FROM pets", [], "SELECT")

    def test_appends_where_when_absent(self) -> None:
        policy = _policy()
        host = _Host(policy)
        with policy.activate(user_id=42):
            query, params = host._rls_apply("SELECT * FROM pets", [], "SELECT")
        assert query == "SELECT * FROM pets WHERE user_id = ?"
        assert params == [42]

    def test_ands_into_existing_where(self) -> None:
        policy = _policy()
        host = _Host(policy)
        with policy.activate(user_id=42):
            query, params = host._rls_apply(
                "SELECT * FROM pets WHERE owner = ?",
                ["bob"],
                "SELECT",
            )
        assert query == "SELECT * FROM pets WHERE owner = ? AND user_id = ?"
        assert params == ["bob", 42]

    def test_case_insensitive_where_detection(self) -> None:
        policy = _policy()
        host = _Host(policy)
        with policy.activate(user_id=42):
            query, params = host._rls_apply("select * from pets where x = 1", [], "SELECT")
        assert "where x = 1 AND user_id = ?" in query
        assert params == [42]

    def test_admin_bypass_skips_predicate(self) -> None:
        policy = _policy()
        host = _Host(policy)
        with policy.activate(user_id=42):
            with policy.admin_bypass(reason="test", table="pets"):
                query, params = host._rls_apply("SELECT * FROM pets", [], "SELECT")
        assert query == "SELECT * FROM pets"
        assert params == []

    def test_multiple_scope_columns(self) -> None:
        policy = RowLevelSecurityPolicy(columns=[ScopeColumn("user_id"), ScopeColumn("tenant_id")])
        host = _Host(policy)
        with policy.activate(user_id=1, tenant_id="acme"):
            query, params = host._rls_apply("SELECT 1", [], "SELECT")
        assert query == "SELECT 1 WHERE user_id = ? AND tenant_id = ?"
        assert params == [1, "acme"]


class TestValidateInsert:
    def test_no_policy_allows(self) -> None:
        _Host(None)._rls_validate_insert({})  # must not raise

    def test_requires_scope_columns(self) -> None:
        host = _Host(_policy())
        with pytest.raises(ValueError, match="user_id"):
            host._rls_validate_insert({"name": "rex"})

    def test_none_value_rejected(self) -> None:
        host = _Host(_policy())
        with pytest.raises(ValueError, match="missing or None"):
            host._rls_validate_insert({"user_id": None})

    def test_valid_insert_passes(self) -> None:
        host = _Host(_policy())
        host._rls_validate_insert({"user_id": 7, "name": "rex"})

    def test_admin_bypass_allows_missing(self) -> None:
        policy = _policy()
        host = _Host(policy)
        with policy.admin_bypass(reason="test", table="pets"):
            host._rls_validate_insert({"name": "rex"})  # must not raise


class TestAdminScope:
    async def test_bypass_active_inside_block(self) -> None:
        policy = _policy()
        host = _Host(policy)
        with policy.activate(user_id=42):
            async with host.with_admin_scope(reason="ticket-99"):
                assert policy.is_admin_bypass_active() is True
            assert policy.is_admin_bypass_active() is False

    async def test_no_policy_raises(self) -> None:
        host = _Host(None)
        with pytest.raises(RuntimeError, match=r"no .*RowLevelSecurityPolicy"):
            async with host.with_admin_scope(reason="x"):
                pass  # pragma: no cover

    async def test_bypass_restores_even_on_error(self) -> None:
        policy = _policy()
        host = _Host(policy)
        with pytest.raises(RuntimeError, match="body"):
            async with host.with_admin_scope(reason="ticket-99"):
                raise RuntimeError("body")
        assert policy.is_admin_bypass_active() is False
