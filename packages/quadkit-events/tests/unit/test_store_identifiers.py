"""Unit tests for events store SQL identifier validation."""

from __future__ import annotations

import pytest

from quadkit.events.stores.identifiers import (
    MAX_SQL_IDENTIFIER_LENGTH,
    validate_table_name,
)


class TestValidateTableName:
    """Identifier-shape validation for interpolated table names."""

    def test_accepts_plain_identifier(self) -> None:
        validate_table_name("event_idempotency")
        validate_table_name("event_checkpoints")
        validate_table_name("Tenant42_events")
        validate_table_name("_private")

    def test_accepts_max_length_identifier(self) -> None:
        validate_table_name("a" * MAX_SQL_IDENTIFIER_LENGTH)

    def test_rejects_overlong_identifier(self) -> None:
        with pytest.raises(ValueError, match="at most"):
            validate_table_name("a" * (MAX_SQL_IDENTIFIER_LENGTH + 1))

    def test_rejects_leading_digit(self) -> None:
        with pytest.raises(ValueError, match="pattern"):
            validate_table_name("1events")

    def test_rejects_sql_metacharacters(self) -> None:
        for name in ("events; DROP TABLE events", "events--", "events'", 'events"'):
            with pytest.raises(ValueError, match="Invalid table name"):
                validate_table_name(name)

    def test_rejects_whitespace(self) -> None:
        with pytest.raises(ValueError, match="Invalid table name"):
            validate_table_name("event table")

    def test_rejects_hyphen(self) -> None:
        with pytest.raises(ValueError, match="Invalid table name"):
            validate_table_name("event-table")

    def test_rejects_empty_string(self) -> None:
        with pytest.raises(ValueError, match="Invalid table name"):
            validate_table_name("")
