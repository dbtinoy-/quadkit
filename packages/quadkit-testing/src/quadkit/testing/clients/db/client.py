from __future__ import annotations

from typing import Any, Self


class DatabaseTestClient:
    def __init__(self, connection_string: str = ":memory:", auto_cleanup: bool = True):
        self.connection_string = connection_string
        self.auto_cleanup = auto_cleanup
        self._pool: Any = None
        self._connection: Any = None
        self._tables_created: list[str] = []
        self._table_data: dict[str, list[dict]] = {}
        self._connected: bool = False

    async def __aenter__(self) -> Self:
        self._connected = True
        self._pool = "mock_pool"
        self._connection = "mock_connection"
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        if self.auto_cleanup:
            await self.cleanup()
        self._connected = False
        self._pool = None
        self._connection = None

    async def cleanup(self) -> None:
        """Drop tracked tables and clear table data."""
        self._tables_created = []
        self._table_data = {}

    async def connect(self) -> None:
        self._connected = True
        self._pool = "mock_pool"
        self._connection = "mock_connection"

    async def disconnect(self) -> None:
        self._connected = False
        self._pool = None
        self._connection = None
        self._tables_created = []

    def _check_connected(self) -> None:
        if not self._connected:
            raise RuntimeError("Not connected to database")

    async def execute_query(self, query: str, params: list | None = None) -> list[dict]:
        self._check_connected()
        return []

    async def execute(
        self, query: str, params: list | None = None, fetch: bool = True
    ) -> list[dict] | int:
        self._check_connected()
        if not fetch:
            # Simulate INSERT rowcount: count values placeholders
            return 1
        table_name = self._extract_table_from_query(query)
        if table_name and table_name in self._table_data:
            return list(self._table_data[table_name])
        return []

    def _extract_table_from_query(self, query: str) -> str | None:
        query_lower = query.lower()
        if "from" in query_lower:
            parts = query_lower.split("from")[1].strip().split()
            if parts:
                return parts[0].rstrip(";,")
        return None

    async def create_table(self, name: str, schema: dict | str) -> None:
        self._check_connected()
        self._tables_created.append(name)
        self._table_data[name] = []

    async def drop_table(self, name: str) -> None:
        self._check_connected()
        if name in self._tables_created:
            self._tables_created.remove(name)
        if name in self._table_data:
            del self._table_data[name]

    async def clear_table(self, name: str) -> None:
        self._check_connected()
        if name in self._table_data:
            self._table_data[name] = []

    async def get_table_count(self, table_name: str) -> int:
        self._check_connected()
        return len(self._table_data.get(table_name, []))

    async def insert_data(self, table: str, data: dict | list[dict]) -> int:
        self._check_connected()
        if isinstance(data, dict):
            data = [data]
        if table not in self._table_data:
            self._table_data[table] = []
        self._table_data[table].extend(data)
        return len(data)

    async def insert(self, table: str, data: dict | list[dict]) -> int:
        return await self.insert_data(table, data)
