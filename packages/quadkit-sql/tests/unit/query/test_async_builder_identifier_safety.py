"""AsyncQueryBuilder identifier-safety tests (F3)."""

from __future__ import annotations

import pytest

from quadkit.contracts.data import InvalidIdentifierError
from quadkit.contracts.data.identifiers import Column
from quadkit.sql.query import AsyncQueryBuilder, Operator

PAYLOAD = "id'; DROP TABLE users;--"


class TestIdentifierSafety:
    """Every column-named builder API rejects invalid identifiers at set-time."""

    def test_where_rejects_payload(self) -> None:
        with pytest.raises(InvalidIdentifierError):
            AsyncQueryBuilder("users").where(PAYLOAD, Operator.EQ, 1)

    def test_select_rejects_payload(self) -> None:
        with pytest.raises(InvalidIdentifierError):
            AsyncQueryBuilder("users").select(PAYLOAD)

    def test_or_where_rejects_payload(self) -> None:
        with pytest.raises(InvalidIdentifierError):
            AsyncQueryBuilder("users").or_where(PAYLOAD, Operator.EQ, 1)

    def test_where_between_rejects_payload(self) -> None:
        with pytest.raises(InvalidIdentifierError):
            AsyncQueryBuilder("users").where_between(PAYLOAD, 1, 10)

    def test_where_not_between_rejects_payload(self) -> None:
        with pytest.raises(InvalidIdentifierError):
            AsyncQueryBuilder("users").where_not_between(PAYLOAD, 1, 10)

    def test_where_in_subquery_rejects_payload(self) -> None:
        with pytest.raises(InvalidIdentifierError):
            AsyncQueryBuilder("users").where_in_subquery(
                PAYLOAD, "SELECT id FROM orders"
            )

    def test_where_not_in_subquery_rejects_payload(self) -> None:
        with pytest.raises(InvalidIdentifierError):
            AsyncQueryBuilder("users").where_not_in_subquery(
                PAYLOAD, "SELECT id FROM orders"
            )

    def test_group_by_rejects_payload(self) -> None:
        with pytest.raises(InvalidIdentifierError):
            AsyncQueryBuilder("users").group_by(PAYLOAD)

    def test_having_rejects_payload(self) -> None:
        with pytest.raises(InvalidIdentifierError):
            AsyncQueryBuilder("users").having(PAYLOAD, Operator.GT, 5)

    def test_order_by_rejects_payload(self) -> None:
        with pytest.raises(InvalidIdentifierError):
            AsyncQueryBuilder("users").order_by(PAYLOAD)

    def test_distinct_rejects_payload(self) -> None:
        with pytest.raises(InvalidIdentifierError):
            AsyncQueryBuilder("users").distinct(PAYLOAD)

    def test_on_conflict_rejects_payload(self) -> None:
        with pytest.raises(InvalidIdentifierError):
            AsyncQueryBuilder("users").on_conflict(PAYLOAD)

    def test_returning_rejects_payload(self) -> None:
        with pytest.raises(InvalidIdentifierError):
            AsyncQueryBuilder("users").returning(PAYLOAD)

    def test_select_sum_rejects_payload(self) -> None:
        with pytest.raises(InvalidIdentifierError):
            AsyncQueryBuilder("users").select_sum(PAYLOAD)

    def test_select_window_partition_by_rejects_payload(self) -> None:
        with pytest.raises(InvalidIdentifierError):
            AsyncQueryBuilder("users").select_window(
                "ROW_NUMBER()", partition_by=PAYLOAD
            )

    def test_insert_rejects_payload_key(self) -> None:
        with pytest.raises(InvalidIdentifierError):
            AsyncQueryBuilder("users").insert({PAYLOAD: 1})

    def test_update_rejects_payload_key(self) -> None:
        with pytest.raises(InvalidIdentifierError):
            AsyncQueryBuilder("users").update({PAYLOAD: 1})


class TestIdentifierQuoting:
    """Valid identifiers render quoted; values stay parameterized."""

    def test_valid_identifiers_quote(self) -> None:
        qb = (
            AsyncQueryBuilder("users")
            .select("id", "name")
            .where("status", Operator.EQ, "active")
            .order_by("name")
        )
        query = qb.build()
        assert 'SELECT "id", "name"' in query.sql
        assert '"status" = $1' in query.sql
        assert 'ORDER BY "name" ASC' in query.sql
        assert query.params == ("active",)

    def test_select_star_stays_literal(self) -> None:
        qb = AsyncQueryBuilder("users").select("*")
        query = qb.build()
        assert "SELECT *" in query.sql

    def test_select_count_star_renders_count(self) -> None:
        qb = AsyncQueryBuilder("users").select_count("*")
        query = qb.build()
        assert "COUNT(*)" in query.sql

    def test_clean_path_parameterizes_values(self) -> None:
        qb = AsyncQueryBuilder("users").where("id", Operator.IN, [1, 2, 3])
        query = qb.build()
        assert '"id" IN ($1, $2, $3)' in query.sql
        assert query.params == (1, 2, 3)

    def test_select_window_partition_quoted_order_by_raw(self) -> None:
        qb = AsyncQueryBuilder("users").select_window(
            func="ROW_NUMBER()",
            partition_by="dept",
            order_by="created_at DESC",
            alias="rank",
        )
        query = qb.build()
        assert 'PARTITION BY "dept" ORDER BY created_at DESC' in query.sql

    def test_where_stores_column_objects(self) -> None:
        qb = AsyncQueryBuilder("users").where("id", Operator.EQ, 1)
        assert isinstance(qb._wheres[0].column, Column)
        assert qb._wheres[0].column.name == "id"
