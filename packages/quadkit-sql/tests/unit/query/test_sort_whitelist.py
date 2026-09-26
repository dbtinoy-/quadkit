"""ORDER BY / sort identifier-safety tests (F5)."""

from __future__ import annotations

import pytest

from quadkit.contracts.data import InvalidIdentifierError
from quadkit.contracts.data.identifiers import Column
from quadkit.sql.query import AsyncQueryBuilder

PAYLOAD = "id'; DROP TABLE users;--"


class TestSortWhitelist:
    """ORDER BY columns must pass through the Column(identifier) wrap."""

    def test_order_by_rejects_payload(self) -> None:
        with pytest.raises(InvalidIdentifierError):
            AsyncQueryBuilder("users").order_by(PAYLOAD)

    def test_order_by_accepts_valid_whitelist(self) -> None:
        builder = AsyncQueryBuilder("users").order_by("name").order_by("id", desc=True)
        assert len(builder._orders) == 2  # type: ignore[attr-defined]

    def test_order_by_sql_injection_payload_key_is_rejected(self) -> None:
        with pytest.raises(InvalidIdentifierError):
            AsyncQueryBuilder("users").order_by("created_at").order_by(PAYLOAD)

    def test_build_quotes_order_by(self) -> None:
        query = AsyncQueryBuilder("users").order_by("name").build()
        assert 'ORDER BY "name" ASC' in query.sql

    def test_build_quotes_order_by_desc(self) -> None:
        query = AsyncQueryBuilder("users").order_by("name", desc=True).build()
        assert 'ORDER BY "name" DESC' in query.sql

    def test_valid_builder_still_works(self) -> None:
        query = (
            AsyncQueryBuilder("users")
            .where("active", "=", True)
            .order_by("created_at", desc=True)
            .limit(10)
            .build()
        )
        assert 'FROM "users"' in query.sql
        assert query.params == (True, 10)


def test_column_wrap_quotes_identifiers() -> None:
    assert str(Column("name")) == '"name"'
    with pytest.raises(InvalidIdentifierError):
        Column(PAYLOAD)
