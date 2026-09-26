"""Tests for Quadkit DB AsyncQueryBuilder"""

from unittest.mock import AsyncMock

import pytest

from quadkit.contracts.data.identifiers import Table
from quadkit.sql.query import (
    AsyncQueryBuilder,
    Operator,
)


class TestAsyncQueryBuilder:
    """Test AsyncQueryBuilder"""

    def test_basic_select(self):
        """Test basic SELECT query"""
        qb = AsyncQueryBuilder("users")
        assert qb._table == Table("users")
        assert qb._selects == ["*"]

    def test_select_columns(self):
        """Test SELECT with specific columns"""
        qb = AsyncQueryBuilder("users").select("id", "name", "email")
        assert [c.name for c in qb._selects] == ["id", "name", "email"]

    def test_where_conditions(self):
        """Test WHERE conditions"""
        qb = (
            AsyncQueryBuilder("users")
            .where("active", Operator.EQ, True)
            .where("name", Operator.LIKE, "John%")
            .where("id", Operator.IN, [1, 2, 3])
        )

        assert len(qb._wheres) == 3
        assert qb._wheres[0].column.name == "active"
        assert qb._wheres[0].operator == Operator.EQ
        assert qb._wheres[0].value is True

        assert qb._wheres[1].column.name == "name"
        assert qb._wheres[1].operator == Operator.LIKE
        assert qb._wheres[1].value == "John%"

        assert qb._wheres[2].column.name == "id"
        assert qb._wheres[2].operator == Operator.IN
        assert qb._wheres[2].value == [1, 2, 3]

    def test_order_by(self):
        """Test ORDER BY clauses"""
        qb = (
            AsyncQueryBuilder("users")
            .order_by("name", desc=False)
            .order_by("created_at", desc=True)
        )

        assert len(qb._orders) == 2
        assert qb._orders[0].column.name == "name"
        assert qb._orders[0].desc is False
        assert qb._orders[1].column.name == "created_at"
        assert qb._orders[1].desc is True

    def test_limit_offset(self):
        """Test LIMIT and OFFSET"""
        qb = AsyncQueryBuilder("users").limit(10).offset(20)
        assert qb._limit == 10
        assert qb._offset == 20

    def test_build_select(self):
        """Test query building"""
        qb = (
            AsyncQueryBuilder("users")
            .select("id", "name")
            .where("active", Operator.EQ, True)
            .order_by("name")
            .limit(5)
        )

        query = qb.build()

        # Expected SQL for generic/postgres style in builder.py
        # SELECT "id", "name" FROM "users" WHERE "active" = $1 ORDER BY "name" ASC LIMIT $2

        assert 'SELECT "id", "name" FROM "users"' in query.sql
        assert '"active" = $1' in query.sql
        assert 'ORDER BY "name" ASC' in query.sql
        assert "LIMIT $2" in query.sql
        assert query.params == (True, 5)

    def test_insert_query(self):
        """Test INSERT query building"""
        data = {"name": "John", "email": "john@example.com"}
        qb = AsyncQueryBuilder("users").insert(data)

        query = qb.build()
        # INSERT INTO "users" ("name", "email") VALUES ($1, $2)
        # Note: dict order preservation is standard in modern Python

        assert 'INSERT INTO "users"' in query.sql
        assert '"name"' in query.sql
        assert '"email"' in query.sql
        assert "VALUES" in query.sql
        assert len(query.params) == 2
        assert "John" in query.params
        assert "john@example.com" in query.params

    def test_update_query(self):
        """Test UPDATE query building"""
        data = {"name": "Updated Name", "active": False}
        qb = AsyncQueryBuilder("users").update(data).where("id", Operator.EQ, 1)

        query = qb.build()

        assert 'UPDATE "users" SET' in query.sql
        assert '"name" = $' in query.sql  # regex match might be safer or substring
        assert 'WHERE "id" = $' in query.sql

        # Verify params order: set params first, then where params
        # builder.py implementation sorts keys for determinism: active, name
        # active=$1, name=$2, id=$3

        # Check params content
        assert False in query.params
        assert "Updated Name" in query.params
        assert 1 in query.params

    def test_delete_query(self):
        """Test DELETE query building"""
        qb = AsyncQueryBuilder("users").delete().where("id", Operator.EQ, 1)

        query = qb.build()

        assert 'DELETE FROM "users" WHERE "id" = $1' in query.sql
        assert query.params == (1,)

    def test_update_requires_where(self):
        """Test UPDATE safeguards"""
        qb = AsyncQueryBuilder("users").update({"a": 1})
        with pytest.raises(ValueError, match="must have WHERE"):
            qb.build()

    def test_delete_requires_where(self):
        """Test DELETE safeguards"""
        qb = AsyncQueryBuilder("users").delete()
        with pytest.raises(ValueError, match="must have WHERE"):
            qb.build()

    @pytest.mark.asyncio
    async def test_execute_select(self):
        """Test SELECT execution dispatch"""
        mock_conn = AsyncMock()
        mock_conn.fetch.return_value = [{"id": 1}]

        qb = AsyncQueryBuilder("users")
        result = await qb.execute(mock_conn)

        mock_conn.fetch.assert_called_once()
        assert result == [{"id": 1}]

    @pytest.mark.asyncio
    async def test_execute_insert(self):
        """Test INSERT execution dispatch"""
        mock_conn = AsyncMock()
        mock_conn.execute.return_value = "INSERT 0 1"

        qb = AsyncQueryBuilder("users").insert({"a": 1})
        await qb.execute(mock_conn)

        mock_conn.execute.assert_called_once()
