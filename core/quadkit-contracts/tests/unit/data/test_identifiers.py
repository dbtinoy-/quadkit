"""Tests for SQL identifiers."""

from __future__ import annotations

import pytest

from quadkit.contracts.data.identifiers import (
    Column,
    Identifier,
    QualifiedTable,
    Schema,
    Table,
    column,
    schema,
    table,
)
from quadkit.contracts.data.sql.sql import InvalidIdentifierError
from quadkit.contracts.data.sql.sql_dialect import SQLDialect


class TestIdentifier:
    """Tests for Identifier class."""

    def test_create_valid_identifier(self) -> None:
        """Verify valid identifier is created."""
        ident = Identifier("users")
        assert ident.name == "users"
        assert ident.quoted == '"users"'

    def test_identifier_str_returns_quoted(self) -> None:
        """Verify __str__ returns quoted form."""
        ident = Identifier("users")
        assert str(ident) == '"users"'

    def test_identifier_repr(self) -> None:
        """Verify __repr__ returns raw name."""
        ident = Identifier("users")
        assert repr(ident) == "Identifier('users')"

    def test_identifier_equality(self) -> None:
        """Verify equality works."""
        id1 = Identifier("users")
        id2 = Identifier("users")
        assert id1 == id2

    def test_identifier_inequality_different_name(self) -> None:
        """Verify inequality for different names."""
        id1 = Identifier("users")
        id2 = Identifier("posts")
        assert id1 != id2

    def test_identifier_inequality_different_dialect(self) -> None:
        """Verify inequality for different dialects."""
        from quadkit.contracts.data.sql.sql_dialect import SQLDialect

        id1 = Identifier("users", dialect=SQLDialect.POSTGRESQL)
        id2 = Identifier("users", dialect=SQLDialect.MYSQL)
        assert id1 != id2

    def test_identifier_hash(self) -> None:
        """Verify hashing works."""
        id1 = Identifier("users")
        id2 = Identifier("users")
        assert hash(id1) == hash(id2)

    def test_identifier_is_reserved(self) -> None:
        """Verify reserved word detection."""
        ident = Identifier("SELECT")
        assert ident.is_reserved is True

    def test_identifier_not_reserved(self) -> None:
        """Verify non-reserved word."""
        ident = Identifier("users")
        assert ident.is_reserved is False

    def test_mysql_quoting(self) -> None:
        """Verify MySQL quoting."""
        ident = Identifier("users", dialect=SQLDialect.MYSQL)
        assert ident.quoted == "`users`"

    def test_postgres_quoting(self) -> None:
        """Verify PostgreSQL quoting."""
        ident = Identifier("users", dialect=SQLDialect.POSTGRESQL)
        assert ident.quoted == '"users"'

    def test_invalid_empty_name_raises(self) -> None:
        """Verify empty name raises."""
        with pytest.raises(InvalidIdentifierError):
            Identifier("")

    def test_invalid_chars_raises(self) -> None:
        """Verify invalid characters raise."""
        with pytest.raises(InvalidIdentifierError):
            Identifier("users-table")

    def test_starts_with_number_raises(self) -> None:
        """Verify starting with number raises."""
        with pytest.raises(InvalidIdentifierError):
            Identifier("123users")

    def test_exceeds_max_length_raises(self) -> None:
        """Verify max length enforcement."""
        with pytest.raises(InvalidIdentifierError):
            Identifier("a" * 100, dialect=SQLDialect.POSTGRESQL)


class TestTable:
    """Tests for Table class."""

    def test_table_creation(self) -> None:
        """Verify table creation."""
        t = Table("users")
        assert t.name == "users"

    def test_table_in_string_interpolation(self) -> None:
        """Verify table works in string interpolation."""
        t = Table("users")
        query = f"SELECT * FROM {t}"
        assert query == 'SELECT * FROM "users"'


class TestColumn:
    """Tests for Column class."""

    def test_column_creation(self) -> None:
        """Verify column creation."""
        c = Column("email")
        assert c.name == "email"

    def test_column_in_string_interpolation(self) -> None:
        """Verify column works in string interpolation."""
        c = Column("email")
        query = f"SELECT {c} FROM users"
        assert query == 'SELECT "email" FROM users'


class TestSchema:
    """Tests for Schema class."""

    def test_schema_creation(self) -> None:
        """Verify schema creation."""
        s = Schema("public")
        assert s.name == "public"


class TestQualifiedTable:
    """Tests for QualifiedTable class."""

    def test_qualified_table_creation(self) -> None:
        """Verify qualified table creation."""
        qt = QualifiedTable(Schema("public"), Table("users"))
        assert qt.schema.name == "public"
        assert qt.table.name == "users"

    def test_qualified_table_quoted(self) -> None:
        """Verify quoted form."""
        qt = QualifiedTable(Schema("public"), Table("users"))
        assert qt.quoted == '"public"."users"'

    def test_qualified_table_str(self) -> None:
        """Verify __str__ returns quoted form."""
        qt = QualifiedTable(Schema("public"), Table("users"))
        assert str(qt) == '"public"."users"'

    def test_qualified_table_equality(self) -> None:
        """Verify equality."""
        qt1 = QualifiedTable(Schema("public"), Table("users"))
        qt2 = QualifiedTable(Schema("public"), Table("users"))
        assert qt1 == qt2


class TestCachedFactories:
    """Tests for cached factory functions."""

    def test_table_cached(self) -> None:
        """Verify table caching works."""
        t1 = table("users")
        t2 = table("users")
        assert t1 is t2

    def test_column_cached(self) -> None:
        """Verify column caching works."""
        c1 = column("email")
        c2 = column("email")
        assert c1 is c2

    def test_schema_cached(self) -> None:
        """Verify schema caching works."""
        s1 = schema("public")
        s2 = schema("public")
        assert s1 is s2

    def test_table_with_dialect(self) -> None:
        """Verify table with dialect."""
        t = table("users", dialect=SQLDialect.MYSQL)
        assert t.quoted == "`users`"

    def test_column_with_dialect(self) -> None:
        """Verify column with dialect."""
        c = column("email", dialect=SQLDialect.MYSQL)
        assert c.quoted == "`email`"

    def test_schema_with_dialect(self) -> None:
        """Verify schema with dialect."""
        s = schema("public", dialect=SQLDialect.MYSQL)
        assert s.quoted == "`public`"