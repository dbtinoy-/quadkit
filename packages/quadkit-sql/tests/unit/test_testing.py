"""Unit tests for database testing utilities"""

import pytest

# Skip this module if `quadkit.testing` isn't importable in this environment.
# pytest.importorskip("quadkit.testing")
try:
    from quadkit.testing import DatabaseTestBed, DatabaseTestClient
except ImportError:
    DatabaseTestBed = None
    DatabaseTestClient = None


@pytest.mark.skipif(DatabaseTestClient is None, reason="quadkit.testing not available")
class TestDatabaseTestClient:
    """Test DatabaseTestClient functionality"""

    @pytest.fixture
    def client(self):
        """Create a test client"""
        return DatabaseTestClient(":memory:")

    @pytest.mark.asyncio
    async def test_client_creation(self, client):
        """Test client creation"""
        assert client.connection_string == ":memory:"
        assert client.auto_cleanup is True
        assert client._pool is None
        assert client._connection is None
        assert client._tables_created == []

    @pytest.mark.asyncio
    async def test_context_manager(self, client):
        """Test client as async context manager"""
        async with client:
            assert client._pool is not None
            assert client._connection is not None

        # Should be cleaned up
        assert client._pool is None
        assert client._connection is None

    @pytest.mark.asyncio
    async def test_execute_query_with_results(self, client):
        """Test executing a query that returns results"""
        async with client:
            # Create a test table
            await client.create_table("test_users", "id INTEGER PRIMARY KEY, name TEXT")

            # Insert data
            await client.insert_data(
                "test_users", [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}],
            )

            # Query data
            results = await client.execute("SELECT * FROM test_users ORDER BY id")

            assert len(results) == 2
            assert results[0]["name"] == "Alice"
            assert results[1]["name"] == "Bob"

    @pytest.mark.asyncio
    async def test_execute_query_no_results(self, client):
        """Test executing a query that doesn't return results"""
        async with client:
            await client.create_table("test_table", "id INTEGER PRIMARY KEY")

            # Insert should return row count
            result = await client.execute(
                "INSERT INTO test_table (id) VALUES (1)", fetch=False,
            )

            assert isinstance(result, int)
            assert result == 1  # rowcount

    @pytest.mark.asyncio
    async def test_create_table(self, client):
        """Test table creation"""
        async with client:
            await client.create_table("test_table", "id INTEGER PRIMARY KEY, name TEXT")

            assert "test_table" in client._tables_created

            # Verify table exists by inserting data
            await client.insert_data("test_table", {"id": 1, "name": "test"})
            count = await client.get_table_count("test_table")
            assert count == 1

    @pytest.mark.asyncio
    async def test_insert_data_single_row(self, client):
        """Test inserting single row of data"""
        async with client:
            await client.create_table(
                "users", "id INTEGER PRIMARY KEY, name TEXT, email TEXT",
            )

            inserted = await client.insert_data(
                "users", {"id": 1, "name": "John", "email": "john@example.com"},
            )

            assert inserted == 1
            count = await client.get_table_count("users")
            assert count == 1

    @pytest.mark.asyncio
    async def test_insert_data_multiple_rows(self, client):
        """Test inserting multiple rows of data"""
        async with client:
            await client.create_table("users", "id INTEGER PRIMARY KEY, name TEXT")

            data = [
                {"id": 1, "name": "Alice"},
                {"id": 2, "name": "Bob"},
                {"id": 3, "name": "Charlie"},
            ]

            inserted = await client.insert_data("users", data)

            assert inserted == 3
            count = await client.get_table_count("users")
            assert count == 3

    @pytest.mark.asyncio
    async def test_clear_table(self, client):
        """Test clearing table data"""
        async with client:
            await client.create_table("users", "id INTEGER PRIMARY KEY, name TEXT")

            # Insert data
            await client.insert_data(
                "users", [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}],
            )

            # Verify data exists
            count = await client.get_table_count("users")
            assert count == 2

            # Clear table
            await client.clear_table("users")

            # Verify data is gone
            count = await client.get_table_count("users")
            assert count == 0

    @pytest.mark.asyncio
    async def test_drop_table(self, client):
        """Test dropping a table"""
        async with client:
            await client.create_table("test_table", "id INTEGER PRIMARY KEY")

            assert "test_table" in client._tables_created

            await client.drop_table("test_table")

            assert "test_table" not in client._tables_created

    @pytest.mark.asyncio
    async def test_get_table_count(self, client):
        """Test getting table row count"""
        async with client:
            await client.create_table("users", "id INTEGER PRIMARY KEY, name TEXT")

            # Empty table
            count = await client.get_table_count("users")
            assert count == 0

            # Add data
            await client.insert_data(
                "users", [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}],
            )

            count = await client.get_table_count("users")
            assert count == 2

    # @pytest.mark.asyncio
    # async def test_transaction_context_manager(self, client):
    #     """Test transaction context manager"""
    #     async with client:
    #         await client.create_table("users", "id INTEGER PRIMARY KEY, name TEXT")

    #         async with client.transaction():
    #             await client.execute("INSERT INTO users (id, name) VALUES (1, 'Alice')", fetch=False)
    #             await client.execute("INSERT INTO users (id, name) VALUES (2, 'Bob')", fetch=False)

    #         # Transaction should be committed
    #         count = await client.get_table_count("users")
    #         assert count == 2

    @pytest.mark.asyncio
    async def test_cleanup_auto_cleanup_enabled(self, client):
        """Test automatic cleanup when enabled"""
        async with client:
            await client.create_table("table1", "id INTEGER PRIMARY KEY")
            await client.create_table("table2", "id INTEGER PRIMARY KEY")

            assert len(client._tables_created) == 2

        # Tables should be dropped automatically
        assert len(client._tables_created) == 0

    @pytest.mark.asyncio
    async def test_cleanup_auto_cleanup_disabled(self):
        """Test no cleanup when disabled"""
        client = DatabaseTestClient(":memory:", auto_cleanup=False)

        async with client:
            await client.create_table("table1", "id INTEGER PRIMARY KEY")

            assert len(client._tables_created) == 1

        # Tables should not be dropped
        assert len(client._tables_created) == 1

        # Manual cleanup
        await client.cleanup()
        assert len(client._tables_created) == 0

    @pytest.mark.asyncio
    async def test_execute_without_connection_raises_error(self, client):
        """Test executing query without connection raises error"""
        with pytest.raises(RuntimeError, match="Not connected to database"):
            await client.execute("SELECT 1")


@pytest.mark.skipif(DatabaseTestBed is None, reason="quadkit.testing not available")
class TestDatabaseTestBed:
    """Test DatabaseTestBed functionality"""

    @pytest.fixture
    def test_bed(self):
        """Create a test bed"""
        return DatabaseTestBed("test-bed", ":memory:")

    @pytest.mark.asyncio
    async def test_test_bed_creation(self, test_bed):
        """Test test bed creation"""
        assert test_bed.name == "test-bed"
        assert test_bed.connection_string == ":memory:"
        assert test_bed.auto_cleanup is True
        assert isinstance(test_bed.client, DatabaseTestClient)

    @pytest.mark.asyncio
    async def test_test_bed_context_manager(self, test_bed):
        """Test test bed as context manager"""
        async with test_bed:
            assert test_bed.client._pool is not None
            assert test_bed.client._connection is not None

        # Should be cleaned up
        assert test_bed.client._pool is None
        assert test_bed.client._connection is None

    @pytest.mark.asyncio
    async def test_create_test_table(self, test_bed):
        """Test creating test table via test bed"""
        async with test_bed:
            await test_bed.create_test_table(
                "users", "id INTEGER PRIMARY KEY, name TEXT",
            )

            # Verify table exists
            count = await test_bed.client.get_table_count("users")
            assert count == 0  # Empty table

    @pytest.mark.asyncio
    async def test_seed_test_data(self, test_bed):
        """Test seeding test data via test bed"""
        async with test_bed:
            await test_bed.create_test_table(
                "users", "id INTEGER PRIMARY KEY, name TEXT",
            )

            data = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]

            await test_bed.seed_test_data("users", data)

            count = await test_bed.client.get_table_count("users")
            assert count == 2

    @pytest.mark.asyncio
    async def test_clear_test_data(self, test_bed):
        """Test clearing test data via test bed"""
        async with test_bed:
            await test_bed.create_test_table(
                "users", "id INTEGER PRIMARY KEY, name TEXT",
            )

            # Seed data
            await test_bed.seed_test_data("users", [{"id": 1, "name": "Alice"}])

            # Verify data exists
            count = await test_bed.client.get_table_count("users")
            assert count == 1

            # Clear data
            await test_bed.clear_test_data("users")

            # Verify data is gone
            count = await test_bed.client.get_table_count("users")
            assert count == 0


@pytest.mark.skipif(DatabaseTestBed is None, reason="quadkit.testing not available")
class TestSampleDataFixtures:
    """Test sample data fixtures"""

    def test_sample_user_data(self, sample_user_data):
        """Test sample user data fixture"""
        assert isinstance(sample_user_data, list)
        assert len(sample_user_data) == 3

        user = sample_user_data[0]
        assert "id" in user
        assert "name" in user
        assert "email" in user
        assert "role" in user

    def test_sample_order_data(self, sample_order_data):
        """Test sample order data fixture"""
        assert isinstance(sample_order_data, list)
        assert len(sample_order_data) == 3

        order = sample_order_data[0]
        assert "id" in order
        assert "user_id" in order
        assert "total" in order
        assert "status" in order
        assert "items" in order

    def test_sample_product_data(self, sample_product_data):
        """Test sample product data fixture"""
        assert isinstance(sample_product_data, list)
        assert len(sample_product_data) == 3

        product = sample_product_data[0]
        assert "id" in product
        assert "name" in product
        assert "price" in product
        assert "category" in product


@pytest.mark.skipif(DatabaseTestBed is None, reason="quadkit.testing not available")
class TestMockFixtures:
    """Test mock fixtures"""

    def test_mock_connection(self, mock_connection):
        """Test mock connection fixture"""
        assert mock_connection is not None
        assert hasattr(mock_connection, "execute")
        assert hasattr(mock_connection, "fetchone")
        assert hasattr(mock_connection, "fetchall")
        assert hasattr(mock_connection, "close")
        assert hasattr(mock_connection, "transaction")

    def test_mock_connection_pool(self, mock_connection_pool):
        """Test mock connection pool fixture"""
        assert mock_connection_pool is not None
        assert hasattr(mock_connection_pool, "acquire")
        assert hasattr(mock_connection_pool, "release")
        assert hasattr(mock_connection_pool, "close")


@pytest.mark.skipif(DatabaseTestBed is None, reason="quadkit.testing not available")
class TestIntegrationWithFixtures:
    """Test integration with pytest fixtures"""

    @pytest.mark.asyncio
    async def test_db_test_bed_fixture(self, db_test_bed):
        """Test db_test_bed fixture"""
        assert isinstance(db_test_bed, DatabaseTestBed)
        assert db_test_bed.client._pool is not None
        assert db_test_bed.client._connection is not None

    @pytest.mark.asyncio
    async def test_test_database_client_fixture(self, test_database_client):
        """Test test_database_client fixture"""
        assert isinstance(test_database_client, DatabaseTestClient)
        assert test_database_client._pool is not None
        assert test_database_client._connection is not None

    @pytest.mark.asyncio
    async def test_seeded_database_fixture(self, seeded_database):
        """Test seeded_database fixture"""
        # Check users table
        user_count = await seeded_database.client.get_table_count("users")
        assert user_count == 3

        # Check orders table
        order_count = await seeded_database.client.get_table_count("orders")
        assert order_count == 3

        # Check sample data
        users = await seeded_database.client.execute("SELECT * FROM users ORDER BY id")
        assert len(users) == 3
        assert users[0]["name"] == "Alice Johnson"
        assert users[1]["name"] == "Bob Smith"

    @pytest.mark.asyncio
    async def test_clean_database_fixture(self, clean_database):
        """Test clean_database fixture"""
        # Check tables exist but are empty
        user_count = await clean_database.client.get_table_count("users")
        assert user_count == 0

        order_count = await clean_database.client.get_table_count("orders")
        assert order_count == 0

        # Verify we can insert data
        await clean_database.client.insert_data("users", {"id": 1, "name": "Test User"})
        user_count = await clean_database.client.get_table_count("users")
        assert user_count == 1
