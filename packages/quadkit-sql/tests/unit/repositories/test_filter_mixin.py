"""Tests for the repository filter mixin (_FilterMixin._apply_filters_to_query)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from quadkit.sql.exceptions import TenantScopingError
from quadkit.sql.repositories._filter_mixin import _FilterMixin
from quadkit.sql.repositories.filter_objects import F


class _Host(_FilterMixin):
    def __init__(
        self,
        *,
        soft_delete_enabled: bool = False,
        multi_tenant: bool = False,
        tenant_id: str | None = None,
    ) -> None:
        self.soft_delete_enabled = soft_delete_enabled
        self.multi_tenant = multi_tenant
        self.table_name = "orders"
        self._db_ctx = SimpleNamespace(tenant_id=tenant_id) if multi_tenant else None


class TestSoftDelete:
    async def test_soft_delete_filter_appended(self) -> None:
        host = _Host(soft_delete_enabled=True)
        query = await host._apply_filters_to_query("SELECT * FROM orders", [], {})
        assert "deleted_at IS NULL" in query

    async def test_include_deleted_disables_it(self) -> None:
        host = _Host(soft_delete_enabled=True)
        query = await host._apply_filters_to_query(
            "SELECT * FROM orders", [], {}, include_deleted=True
        )
        assert "deleted_at" not in query

    async def test_no_where_when_nothing_applied(self) -> None:
        host = _Host()
        query = await host._apply_filters_to_query("SELECT * FROM orders", [], {})
        assert query == "SELECT * FROM orders"


class TestEqualityFilters:
    async def test_simple_equality(self) -> None:
        host = _Host()
        params: list[Any] = []
        query = await host._apply_filters_to_query("SELECT * FROM orders", params, {"status": "open"})
        assert '"status" = ?' in query
        assert params == ["open"]

    async def test_multiple_equality_anded(self) -> None:
        host = _Host()
        params: list[Any] = []
        query = await host._apply_filters_to_query("SELECT * FROM orders", params, {"a": 1, "b": 2})
        assert '"a" = ?' in query
        assert '"b" = ?' in query
        assert params == [1, 2]

    async def test_string_bool_normalization(self) -> None:
        host = _Host()
        params: list[Any] = []
        await host._apply_filters_to_query("SELECT 1", params, {"flag": "true"})
        assert params == [True]
        params = []
        await host._apply_filters_to_query("SELECT 1", params, {"flag": "off"})
        assert params == [False]

    async def test_list_value_takes_first(self) -> None:
        host = _Host()
        params: list[Any] = []
        await host._apply_filters_to_query("SELECT 1", params, {"status": ["open", "closed"]})
        assert params == ["open"]


class TestOperatorFilters:
    async def test_gt(self) -> None:
        host = _Host()
        params: list[Any] = []
        query = await host._apply_filters_to_query("SELECT 1", params, {"total__gt": 10})
        assert '"total" > ?' in query
        assert params == [10]

    async def test_lte(self) -> None:
        host = _Host()
        params: list[Any] = []
        query = await host._apply_filters_to_query("SELECT 1", params, {"total__lte": 5})
        assert '"total" <= ?' in query

    async def test_in(self) -> None:
        host = _Host()
        params: list[Any] = []
        query = await host._apply_filters_to_query("SELECT 1", params, {"id__in": [1, 2, 3]})
        assert '"id" IN' in query
        assert params == [1, 2, 3]

    async def test_contains(self) -> None:
        host = _Host()
        params: list[Any] = []
        query = await host._apply_filters_to_query("SELECT 1", params, {"note__contains": "abc"})
        assert "LIKE" in query
        assert "%abc%" in params

    async def test_icontains(self) -> None:
        host = _Host()
        params: list[Any] = []
        query = await host._apply_filters_to_query("SELECT 1", params, {"note__icontains": "abc"})
        assert "ILIKE" in query

    async def test_isnull(self) -> None:
        host = _Host()
        params: list[Any] = []
        query = await host._apply_filters_to_query("SELECT 1", params, {"archived_at__isnull": True})
        assert "IS NULL" in query

    async def test_unknown_operator_falls_back_to_equality(self) -> None:
        host = _Host()
        params: list[Any] = []
        query = await host._apply_filters_to_query("SELECT 1", params, {"field__weirdop": 9})
        assert '"field" = ?' in query
        assert params == [9]


class TestDateFilterSkip:
    async def test_date_field_skipped(self) -> None:
        host = _Host()
        params: list[Any] = []
        query = await host._apply_filters_to_query("SELECT 1", params, {"created_at": "2024-01-01"})
        assert "created_at" not in query
        assert params == []

    async def test_date_value_skipped(self) -> None:
        host = _Host()
        params: list[Any] = []
        query = await host._apply_filters_to_query("SELECT 1", params, {"event_day": "2024-01-01"})
        assert "event_day" not in query


class TestTypedFilterExpressions:
    async def test_typed_filter_injected(self) -> None:
        host = _Host()
        params: list[Any] = []
        f = F("status").in_(["a", "b"])
        query = await host._apply_filters_to_query(
            "SELECT * FROM orders", params, {}, filter_expressions=(f,)
        )
        assert '"status" IN (?, ?)' in query
        assert params == ["a", "b"]

    async def test_typed_filter_ands_with_equality(self) -> None:
        host = _Host()
        params: list[Any] = []
        query = await host._apply_filters_to_query(
            "SELECT * FROM orders", params, {"status": "open"}, filter_expressions=(F("id") > 10,)
        )
        assert " AND " in query
        assert params == [10, "open"]


class TestSearch:
    async def test_ilike_search_clause(self) -> None:
        host = _Host()
        params: list[Any] = []
        query = await host._apply_filters_to_query(
            "SELECT * FROM orders",
            params,
            {"search": "acme", "search_fields": ["name", "email"]},
        )
        assert '"name" ILIKE ? OR "email" ILIKE ?' in query
        assert params == ["%acme%", "%acme%"]

    async def test_search_without_fields_ignored(self) -> None:
        host = _Host()
        params: list[Any] = []
        query = await host._apply_filters_to_query(
            "SELECT 1", params, {"search": "acme", "search_fields": []}
        )
        assert "ILIKE" not in query
        assert params == []

    async def test_search_consumes_keys(self) -> None:
        host = _Host()
        params: list[Any] = []
        query = await host._apply_filters_to_query(
            "SELECT 1", params, {"search": "x", "search_fields": ["name"]}
        )
        # the keys are popped, so they must not appear as equality filters
        assert '"search" = ?' not in query
        assert '"search_fields" = ?' not in query


class TestMultiTenant:
    async def test_tenant_scoping_applied(self) -> None:
        host = _Host(multi_tenant=True, tenant_id="acme")
        params: list[Any] = []
        query = await host._apply_filters_to_query("SELECT 1", params, {})
        assert "tenant_id = ?" in query
        assert params == ["acme"]

    async def test_missing_tenant_raises(self) -> None:
        host = _Host(multi_tenant=True, tenant_id=None)
        with pytest.raises(TenantScopingError):
            await host._apply_filters_to_query("SELECT 1", [], {})

    async def test_non_multi_tenant_ignores_tenant(self) -> None:
        host = _Host(multi_tenant=False)
        query = await host._apply_filters_to_query("SELECT 1", [], {})
        assert "tenant_id" not in query


class TestWhereMerging:
    async def test_appends_to_existing_where(self) -> None:
        host = _Host()
        params: list[Any] = []
        query = await host._apply_filters_to_query(
            "SELECT * FROM orders WHERE id > 5", params, {"status": "open"}
        )
        assert query.endswith('WHERE id > 5 AND "status" = ?')

    async def test_fresh_where_when_absent(self) -> None:
        host = _Host()
        params: list[Any] = []
        query = await host._apply_filters_to_query("SELECT * FROM orders", params, {"a": 1})
        assert 'WHERE "a" = ?' in query

    async def test_where_inside_grouping_parenthesis(self) -> None:
        host = _Host()
        params: list[Any] = []
        query = await host._apply_filters_to_query(
            "SELECT * FROM orders WHERE (a = 1)", params, {"b": 2}
        )
        assert query.endswith('WHERE (a = 1) AND "b" = ?')
