"""Tests for database full-text search types."""

import pytest

from quadkit.sql.search.full_text import (
    FTSResult,
    FTSDialect,
    MySQLFTSQuery,
    PostgresFTSQuery,
)


class TestFTSDialect:
    """Tests for FTSDialect enum."""

    def test_fts_dialect_values(self) -> None:
        """Test FTSDialect enum values."""
        assert FTSDialect.POSTGRES.value == "postgres"
        assert FTSDialect.MYSQL.value == "mysql"

    def test_fts_dialect_members(self) -> None:
        """Test FTSDialect has expected members."""
        members = list(FTSDialect)
        assert len(members) == 2


class TestFTSQueryIdentifierValidation:
    """Table/column identifiers are validated before SQL interpolation."""

    @pytest.mark.parametrize(
        ("table", "column"),
        [
            ("docs; DROP TABLE t; --", "title"),
            ("docs", "title') UNION SELECT 1;--"),
            ('"docs"', "title"),
        ],
    )
    def test_postgres_rejects_non_identifiers(self, table: str, column: str) -> None:
        """Invalid table or column names raise ValueError at construction."""
        with pytest.raises(ValueError, match="identifier"):
            PostgresFTSQuery(table=table, columns=[column])

        with pytest.raises(ValueError, match="identifier"):
            MySQLFTSQuery(table=table, columns=[column])

    def test_valid_identifiers_build_sql(self) -> None:
        """Plain identifiers produce valid interpolated SQL."""
        query = PostgresFTSQuery(table="articles", columns=["title", "body"])
        sql, params = query.build("python", limit=5)
        assert "FROM articles" in sql
        assert "coalesce(body::text, '')" in sql
        assert params[1] == "python"

        mysql = MySQLFTSQuery(table="articles", columns=["title", "body"])
        sql, params = mysql.build("python", limit=5)
        assert "FROM articles" in sql
        assert "MATCH(title, body)" in sql
        assert params[0] == "python"


class TestFTSResult:
    """Tests for FTSResult dataclass."""

    def test_fts_result_creation(self) -> None:
        """Test FTSResult creation."""
        result = FTSResult(
            items=["item1", "item2"],
            total=10,
            dialect=FTSDialect.POSTGRES,
        )
        assert result.items == ["item1", "item2"]
        assert result.total == 10
        assert result.dialect == FTSDialect.POSTGRES

    def test_fts_result_iteration(self) -> None:
        """Test FTSResult iteration."""
        result = FTSResult(
            items=["a", "b", "c"],
            total=3,
            dialect=FTSDialect.MYSQL,
        )
        assert list(result) == ["a", "b", "c"]

    def test_fts_result_length(self) -> None:
        """Test FTSResult length."""
        result = FTSResult(
            items=["a", "b"],
            total=5,
            dialect=FTSDialect.POSTGRES,
        )
        assert len(result) == 2
