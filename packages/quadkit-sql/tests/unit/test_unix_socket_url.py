"""Unit tests for libpq Unix-socket query-param parsing in ConnectionManager."""

from __future__ import annotations

from typing import Any

from quadkit.sql.providers.connection_manager import ConnectionManager


class _DummyConnectionManager(ConnectionManager):
    async def _create_connection(self) -> Any:
        return None

    async def _close_connection(self, connection: Any) -> None:
        return None


def test_connection_manager_extracts_unix_socket_host_from_query_string() -> None:
    """ConnectionManager parses ?host=/socket/dir when URL hostname is empty."""
    cm = _DummyConnectionManager(
        "postgresql://postgres:@/piccolina2?host=/var/run/postgresql"
    )
    assert cm.database_type == "postgresql"
    assert cm.host == "/var/run/postgresql"
    assert cm.port is None
    assert cm.database == "piccolina2"
    assert cm.username == "postgres"


def test_connection_manager_prefers_explicit_hostname_over_query_param() -> None:
    """Explicit URL authority hostname takes precedence over ?host=."""
    cm = _DummyConnectionManager(
        "postgresql+asyncpg://app:secret@db.internal:5433/prod?host=/ignored"
    )
    assert cm.database_type == "postgresql"
    assert cm.host == "db.internal"
    assert cm.port == 5433
    assert cm.database == "prod"
    assert cm.username == "app"
    assert cm.password == "secret"
