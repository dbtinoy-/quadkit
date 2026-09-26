"""Tests for events config projections, snapshots, and streaming."""


class TestProjectionConfig:
    """Tests for ProjectionConfig."""

    def test_projection_config_defaults(self) -> None:
        """Test ProjectionConfig has correct defaults."""
        from quadkit.events.config import ProjectionConfig

        config = ProjectionConfig()
        assert config.checkpoint_interval == 100
        assert config.batch_size == 100
        assert config.max_catch_up_events == 10000
        assert config.rebuild_batch_size == 1000
        assert config.enable_parallel_projections is True

    def test_projection_config_custom(self) -> None:
        """Test ProjectionConfig with custom values."""
        from quadkit.events.config import ProjectionConfig

        config = ProjectionConfig(
            checkpoint_interval=50,
            batch_size=50,
            max_catch_up_events=5000,
            rebuild_batch_size=500,
            enable_parallel_projections=False,
        )
        assert config.checkpoint_interval == 50
        assert config.batch_size == 50
        assert config.max_catch_up_events == 5000
        assert config.rebuild_batch_size == 500
        assert config.enable_parallel_projections is False


class TestSnapshotConfig:
    """Tests for SnapshotConfig."""

    def test_snapshot_config_defaults(self) -> None:
        """Test SnapshotConfig has correct defaults."""
        from quadkit.events.config import SnapshotConfig
        from quadkit.events.types import SnapshotStrategy

        config = SnapshotConfig()
        assert config.enabled is True
        assert config.strategy == SnapshotStrategy.EVENT_COUNT
        assert config.event_count_threshold == 100
        assert config.time_threshold_seconds == 3600
        assert config.max_snapshots_per_aggregate == 5

    def test_snapshot_config_custom(self) -> None:
        """Test SnapshotConfig with custom values."""
        from quadkit.events.config import SnapshotConfig
        from quadkit.events.types import SnapshotStrategy

        config = SnapshotConfig(
            enabled=False,
            strategy=SnapshotStrategy.TIME_BASED,
            event_count_threshold=50,
            time_threshold_seconds=1800,
            max_snapshots_per_aggregate=3,
        )
        assert config.enabled is False
        assert config.strategy == SnapshotStrategy.TIME_BASED
        assert config.event_count_threshold == 50
        assert config.time_threshold_seconds == 1800
        assert config.max_snapshots_per_aggregate == 3


class TestStreamingConfig:
    """Tests for StreamingConfig."""

    def test_streaming_config_defaults(self) -> None:
        """Test StreamingConfig has correct defaults."""
        from quadkit.events.config import StreamingConfig

        config = StreamingConfig()
        assert config.buffer_size == 1000
        assert config.batch_size == 100
        assert config.poll_interval_ms == 100
        assert config.max_subscribers == 100
        assert config.enable_websocket is True
        assert config.websocket_ping_interval == 30

    def test_streaming_config_custom(self) -> None:
        """Test StreamingConfig with custom values."""
        from quadkit.events.config import StreamingConfig

        config = StreamingConfig(
            buffer_size=500,
            batch_size=50,
            poll_interval_ms=50,
            max_subscribers=50,
            enable_websocket=False,
            websocket_ping_interval=60,
        )
        assert config.buffer_size == 500
        assert config.batch_size == 50
        assert config.poll_interval_ms == 50
        assert config.max_subscribers == 50
        assert config.enable_websocket is False
        assert config.websocket_ping_interval == 60
