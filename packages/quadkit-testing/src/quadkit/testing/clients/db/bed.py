from __future__ import annotations

from typing import Self

from quadkit.testing.clients.db.client import DatabaseTestClient
from quadkit.testing.fixtures.bed import TestEnvironment


class DatabaseTestBed(TestEnvironment):
    def __init__(
        self,
        name: str = "db-test-bed",
        connection_string: str = ":memory:",
        auto_cleanup: bool = True,
    ):
        super().__init__(name)
        self.connection_string = connection_string
        self.auto_cleanup = auto_cleanup
        self.client = DatabaseTestClient(connection_string, auto_cleanup)

    async def __aenter__(self) -> Self:
        """Enter context: connect the test client."""
        await self.client.__aenter__()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Exit context: disconnect the test client."""
        await self.client.__aexit__(exc_type, exc_val, exc_tb)

    async def create_test_table(self, name: str, schema: str) -> None:
        """Create a test table with the given name and SQL schema string."""
        await self.client.create_table(name, schema)

    async def seed_test_data(self, table: str, data: list[dict] | dict) -> None:
        """Seed test data into a table."""
        await self.client.insert_data(table, data)

    async def clear_test_data(self, table: str) -> None:
        """Clear all rows from a test table."""
        await self.client.clear_table(table)
