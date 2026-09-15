"""Test that all public API symbols are properly exported from quadkit.testing.

This test validates:
1. All documented fakes are exported
2. All 10 compliance suites are exported
3. All memory implementations are exported
4. All test beds and clients are exported
5. All utility assertions are exported
6. Container and fixture helpers are exported
"""


class TestPublicExports:
    """Verify quadkit.testing exports all documented symbols."""

    def test_all_fakes_are_exported(self) -> None:
        """Verify all 12+ fake doubles are exported from quadkit.testing."""
        import quadkit.testing

        fakes_required = [
            "FakeEventBus",
            "FakeLogger",
            "FakeCache",
            "FakeCommandBus",
            "FakeQueryBus",
            "FakeClock",
            "FakeMetricsCollector",
            "FakeConfig",
            "FakeStateStore",
            "FakeUnitOfWork",
            "Clock",  # Base clock interface
            "SystemClock",  # Real clock implementation
            "LogEntry",  # Log entry type for FakeLogger
        ]

        for fake_name in fakes_required:
            assert hasattr(quadkit.testing, fake_name), (
                f"Missing fake export: {fake_name}"
            )
            # Verify it can actually be imported
            obj = getattr(quadkit.testing, fake_name)
            assert obj is not None, f"Fake import returned None: {fake_name}"

    def test_all_compliance_suites_are_exported(self) -> None:
        """Verify all 9 compliance suites are exported from quadkit.testing.

        The conformance architecture requires all suite types to be discoverable.
        Missing compliance suites means implementations can't be tested properly.
        """
        import quadkit.testing

        compliance_required = [
            "EventBusCompliance",
            "RepositoryCompliance",
            "CacheBackendCompliance",
            "DatabaseProviderCompliance",
            "TaskQueueCompliance",
            "BlobStoreCompliance",
            "SearchEngineCompliance",
            "FlagProviderCompliance",
            "MiddlewareCompliance",
        ]

        for suite_name in compliance_required:
            assert hasattr(quadkit.testing, suite_name), (
                f"Missing compliance suite export: {suite_name}"
            )
            obj = getattr(quadkit.testing, suite_name)
            assert obj is not None, (
                f"Compliance suite import returned None: {suite_name}"
            )

    def test_all_memory_implementations_are_exported(self) -> None:
        """Verify all in-memory implementations are exported.

        Memory implementations are critical for unit testing without
        external infrastructure.
        """
        import quadkit.testing

        memory_required = [
            "InMemoryRepository",
            "InMemoryEventBus",
            "InMemoryCommandBus",
            "InMemoryQueryBus",
            "InMemoryUnitOfWork",
            "InMemoryAuditLogger",
            "InMemoryDistributedLock",
            "InMemoryOutbox",
            "OutboxRelay",
            "InMemoryCacheBackend",
            "MemoryProvider",
        ]

        for impl_name in memory_required:
            assert hasattr(quadkit.testing, impl_name), (
                f"Missing memory implementation export: {impl_name}"
            )

    def test_all_test_beds_are_exported(self) -> None:
        """Verify all test bed and client classes are exported."""
        import quadkit.testing

        testbed_required = [
            "AppTestBed",
            "TestEnvironment",
            "WebTestBed",
            "WebTestClient",
            "DatabaseTestBed",
            "DatabaseTestClient",
            "AITestBed",
            "AITestClient",
            "TaskTestBed",
            "TaskTestClient",
        ]

        for testbed_name in testbed_required:
            assert hasattr(quadkit.testing, testbed_name), (
                f"Missing test bed export: {testbed_name}"
            )

    def test_all_container_helpers_are_exported(self) -> None:
        """Verify container helpers are exported."""
        import quadkit.testing

        container_required = [
            "QuadkitContainerHarness",  # Canonical name (replaces TestContainer)
            "ContainerTestFixture",
            "ContainerFactory",
            "override",
        ]

        for helper_name in container_required:
            assert hasattr(quadkit.testing, helper_name), (
                f"Missing container helper export: {helper_name}"
            )

    def test_all_assertions_are_exported(self) -> None:
        """Verify all test assertion helpers are exported."""
        import quadkit.testing

        assertions_required = [
            "assert_result_ok",
            "assert_result_err",
            "assert_ok",
            "assert_err",
            "assert_healthy",
            "assert_all_ok",
            "TestAssertions",
            "TestDataFactory",
            "AsyncTestHelper",
        ]

        for assertion_name in assertions_required:
            assert hasattr(quadkit.testing, assertion_name), (
                f"Missing assertion helper export: {assertion_name}"
            )

    def test_snapshot_utilities_are_exported(self) -> None:
        """Verify snapshot testing utilities are exported."""
        import quadkit.testing

        snapshot_required = [
            "SnapshotAsserter",
            "SnapshotMismatchError",
        ]

        for snapshot_name in snapshot_required:
            assert hasattr(quadkit.testing, snapshot_name), (
                f"Missing snapshot utility export: {snapshot_name}"
            )

    def test_markers_and_probes_are_exported(self) -> None:
        """Verify integration markers and service probes are exported."""
        import quadkit.testing

        markers_required = [
            "requires_redis",
            "requires_postgres",
            "requires_rabbitmq",
            "ServiceProbe",
        ]

        for marker_name in markers_required:
            assert hasattr(quadkit.testing, marker_name), (
                f"Missing marker/probe export: {marker_name}"
            )

    def test_exported_symbols_are_in_all(self) -> None:
        """Verify all documented symbols appear in __all__."""
        import quadkit.testing

        required_in_all = [
            "QuadkitContainerHarness",  # Canonical name (replaces TestContainer)
            "ContainerFactory",
            "FakeEventBus",
            "FakeLogger",
            "CacheBackendCompliance",
            "SnapshotAsserter",
            "AppTestBed",
        ]

        all_list = getattr(quadkit.testing, "__all__", [])
        for symbol in required_in_all:
            assert symbol in all_list, f"Symbol {symbol} not in __all__: {all_list}"

    def test_version_is_accessible(self) -> None:
        """Verify __version__ is accessible."""
        import quadkit.testing

        version = getattr(quadkit.testing, "__version__", None)
        assert version is not None, "Module __version__ not accessible"
        assert isinstance(version, str), "__version__ should be a string"
        assert len(version) > 0, "__version__ should not be empty"

    def test_ai_mocks_are_exported(self) -> None:
        """Verify optional AI mock classes are exported (if available).

        These may not be available if quadkit-ai is not installed.
        """
        import quadkit.testing

        # These are optional — should not fail if not available
        ai_mocks = [
            "MockLLMClient",
            "MockVectorStore",
            "MockClassifier",
        ]

        for mock_name in ai_mocks:
            # Try to access; if it fails, that's okay (optional dependency)
            try:
                obj = getattr(quadkit.testing, mock_name)
                assert obj is not None, f"AI mock import returned None: {mock_name}"
            except AttributeError:
                # Optional dependency not installed
                pass
