"""Tests for events config stores."""

import pytest


class TestInMemoryEventStoreConfig:
    """Tests for InMemoryEventStoreConfig."""

    def test_in_memory_event_store_config_defaults(self) -> None:
        """Test InMemoryEventStoreConfig has correct defaults."""
        from quadkit.events.config import InMemoryEventStoreConfig

        config = InMemoryEventStoreConfig()
        assert config.max_events_per_stream == 10000
        assert config.enable_snapshots is True

    def test_in_memory_event_store_config_custom(self) -> None:
        """Test InMemoryEventStoreConfig with custom values."""
        from quadkit.events.config import InMemoryEventStoreConfig

        config = InMemoryEventStoreConfig(
            max_events_per_stream=5000,
            enable_snapshots=False,
        )
        assert config.max_events_per_stream == 5000
        assert config.enable_snapshots is False


class TestMongoDBEventStoreConfig:
    """Tests for MongoDBEventStoreConfig."""

    def test_mongodb_event_store_config_defaults(self) -> None:
        """Test MongoDBEventStoreConfig has correct defaults."""
        from quadkit.events.config import MongoDBEventStoreConfig

        config = MongoDBEventStoreConfig(connection_string="mongodb://localhost:27017")
        assert config.database_name == "events"
        assert config.events_collection == "domain_events"
        assert config.snapshots_collection == "snapshots"
        assert config.max_pool_size == 10
        assert config.server_selection_timeout == 30000

    def test_mongodb_event_store_config_custom(self) -> None:
        """Test MongoDBEventStoreConfig with custom values."""
        from quadkit.events.config import MongoDBEventStoreConfig

        config = MongoDBEventStoreConfig(
            connection_string="mongodb://localhost:27017",
            database_name="my_db",
            events_collection="my_events",
            snapshots_collection="my_snapshots",
            max_pool_size=5,
            server_selection_timeout=10000,
        )
        assert config.database_name == "my_db"
        assert config.events_collection == "my_events"
        assert config.snapshots_collection == "my_snapshots"
        assert config.max_pool_size == 5
        assert config.server_selection_timeout == 10000

    def test_mongodb_event_store_config_validates_connection_string(self) -> None:
        """Test MongoDBEventStoreConfig validates connection string."""
        from quadkit.events.config import MongoDBEventStoreConfig

        with pytest.raises(ValueError, match="Connection string must start"):
            MongoDBEventStoreConfig(connection_string="invalid://localhost:27017")

    def test_mongodb_event_store_config_accepts_mongodb_plus_srv(self) -> None:
        """Test MongoDBEventStoreConfig accepts mongodb+srv:// connection string."""
        from quadkit.events.config import MongoDBEventStoreConfig

        config = MongoDBEventStoreConfig(connection_string="mongodb+srv://cluster.mongodb.net")
        assert config.connection_string.get_secret_value() == "mongodb+srv://cluster.mongodb.net"


class TestMongoDBConfig:
    """Tests for MongoDBConfig (store-level connection config)."""

    def test_mongodb_config_defaults(self) -> None:
        """Test MongoDBConfig (stores/mongodb) has correct defaults."""
        from quadkit.events.stores.mongodb.config import MongoDBConfig

        config = MongoDBConfig(uri="mongodb://localhost:27017")
        assert config.database == "events"
        assert config.events_collection == "events"
        assert config.snapshots_collection == "snapshots"
        assert config.counters_collection == "counters"
        assert config.max_pool_size == 100
        assert config.auto_create_indexes is True

    def test_mongodb_config_custom(self) -> None:
        """Test MongoDBConfig (stores/mongodb) with custom values."""
        from quadkit.events.stores.mongodb.config import MongoDBConfig

        config = MongoDBConfig(
            uri="mongodb://localhost:27017",
            database="my_db",
            events_collection="my_events",
            snapshots_collection="my_snapshots",
            counters_collection="my_counters",
            max_pool_size=50,
            auto_create_indexes=False,
        )
        assert config.database == "my_db"
        assert config.events_collection == "my_events"
        assert config.snapshots_collection == "my_snapshots"
        assert config.counters_collection == "my_counters"
        assert config.max_pool_size == 50
        assert config.auto_create_indexes is False


class TestSqliteConfig:
    """Tests for SqliteConfig."""

    def test_sqlite_config_defaults(self) -> None:
        """Test SqliteConfig has correct defaults."""
        from quadkit.events.config import SqliteConfig

        config = SqliteConfig()
        assert config.database == "./events.db"
        assert config.pragmas == {}
        assert config.wal_mode is True
        assert config.journal_mode == "WAL"

    def test_sqlite_config_custom(self) -> None:
        """Test SqliteConfig with custom values."""
        from quadkit.events.config import SqliteConfig

        config = SqliteConfig(
            database="./my.db",
            pragmas={"cache_size": 1000},
            wal_mode=False,
            journal_mode="DELETE",
        )
        assert config.database == "./my.db"
        assert config.pragmas == {"cache_size": 1000}
        assert config.wal_mode is False
        assert config.journal_mode == "DELETE"
