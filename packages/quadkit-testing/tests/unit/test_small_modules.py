"""Tests for the small support modules: clock, config, constants, types,
module, integration markers, and the docstring-only scaffold modules.

These modules are small but load-bearing; importing and exercising them
guards the public surface of :mod:`quadkit.testing`.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from quadkit.contracts.core.clock import Duration


# ---------------------------------------------------------------------------
# FixedClock
# ---------------------------------------------------------------------------


def test_fixed_clock_defaults_to_2024_epoch() -> None:
    from quadkit.testing.clock import DEFAULT_FIXED_CLOCK_START, FixedClock

    clock = FixedClock()
    assert clock.now() == DEFAULT_FIXED_CLOCK_START
    assert clock.monotonic() == 0.0
    assert clock.timestamp() == DEFAULT_FIXED_CLOCK_START.timestamp()
    assert clock.time() == clock.timestamp()


def test_fixed_clock_set_and_freeze() -> None:
    from quadkit.testing.clock import FixedClock

    clock = FixedClock()
    target = datetime(2030, 6, 1, 12, 30, tzinfo=UTC)
    clock.set(target)
    assert clock.now() == target
    assert clock.monotonic() == 0.0

    other = datetime(2031, 1, 2, 3, 4, 5, tzinfo=UTC)
    clock.freeze(other)
    assert clock.now() == other


def test_fixed_clock_rejects_naive_datetime() -> None:
    from quadkit.testing.clock import FixedClock

    clock = FixedClock()
    with pytest.raises(ValueError, match="timezone-aware"):
        clock.set(datetime(2024, 1, 1))


def test_fixed_clock_advance_accepts_all_duration_kinds() -> None:
    from quadkit.testing.clock import FixedClock

    clock = FixedClock()
    start = clock.now()

    clock.advance(90.0)
    assert clock.now() == start + timedelta(seconds=90)
    assert clock.monotonic() == 90.0

    clock.advance(timedelta(hours=1))
    assert clock.monotonic() == 3690.0

    clock.advance(Duration.minutes(2))
    assert clock.monotonic() == 3810.0


def test_fixed_clock_tick_advances_one_second() -> None:
    from quadkit.testing.clock import FixedClock

    clock = FixedClock()
    clock.tick()
    assert clock.monotonic() == 1.0
    assert clock.now() == clock.now() + timedelta(0)  # sanity


def test_fixed_clock_normalises_non_utc_timezone() -> None:
    from quadkit.testing.clock import FixedClock

    from datetime import timezone

    plus2 = timezone(timedelta(hours=2))
    clock = FixedClock(initial=datetime(2024, 5, 5, 10, 0, tzinfo=plus2))
    assert clock.now().tzinfo == UTC
    assert clock.now().hour == 8


def test_fixed_clock_backs_the_ambient_seam_for_a_naive_utc_schema() -> None:
    """FixedClock drives an aware/naive-UTC storage seam deterministically.

    This is the shape the reference applications use: production
    reads go through :mod:`quadkit.primitives.clock`, the database stores naive
    UTC, and tests override the ambient clock rather than patching call sites.
    ``FixedClock`` deliberately rejects a naive ``set()`` (see
    ``test_fixed_clock_rejects_naive_datetime``), so a stored naive value is
    lifted with ``replace(tzinfo=UTC)`` — naive means UTC, the invariant both
    apps document.
    """
    from quadkit.primitives import clock as ambient
    from quadkit.testing.clock import FixedClock

    clock = FixedClock(initial=datetime(2026, 3, 4, 5, 6, 7, tzinfo=UTC))
    with ambient.use(clock):
        # aware for logic, naive for the column
        assert ambient.now().tzinfo == UTC
        stored_naive = ambient.now().replace(tzinfo=None)
        assert stored_naive.tzinfo is None
        assert ambient.now().date() == date(2026, 3, 4)

        # advancing moves both projections by the same amount
        clock.advance(3600)
        assert ambient.now().replace(tzinfo=None) - stored_naive == timedelta(hours=1)

        # and a stored naive value round-trips back through set()
        clock.set(stored_naive.replace(tzinfo=UTC))
        assert ambient.now().replace(tzinfo=None) == stored_naive


# ---------------------------------------------------------------------------
# TestingConfig
# ---------------------------------------------------------------------------


def test_testing_config_defaults() -> None:
    from quadkit.testing.config import TestingConfig

    config = TestingConfig()
    assert config.name == "testing"
    assert config.enabled is True
    assert config.db_reuse is True
    assert config.mock_external_services is True
    assert config.cleanup_temp_files is True
    assert TestingConfig.config_section == "testing"


def test_testing_config_accepts_overrides() -> None:
    from quadkit.testing.config import TestingConfig

    config = TestingConfig(db_reuse=False, enabled=False)
    assert config.db_reuse is False
    assert config.enabled is False


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


def test_constants_exports() -> None:
    from quadkit.testing import constants

    assert constants.ENV_PREFIX == "QK_TESTING__"
    assert constants.ENV_NESTED_DELIMITER == "__"
    assert constants.DEFAULT_REDIS_PORT == 6379
    assert constants.DEFAULT_POSTGRES_PORT == 5432
    assert constants.DEFAULT_RABBITMQ_PORT == 5672
    assert constants.DEFAULT_SMTP_PORT == 25
    assert constants.DEFAULT_ELASTICSEARCH_PORT == 9200
    assert constants.DEFAULT_MEILISEARCH_PORT == 7700
    assert constants.MARKER_REDIS == "redis"
    assert constants.MARKER_MEILISEARCH == "meilisearch"
    assert isinstance(constants.__version__, str)


# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------


def test_type_aliases_importable() -> None:
    from quadkit.testing import types

    for name in types.__all__:
        assert getattr(types, name) is not None


# ---------------------------------------------------------------------------
# DI testing module
# ---------------------------------------------------------------------------


def test_testing_module_configure() -> None:
    from quadkit.di.module import DynamicModule
    from quadkit.testing.module import TestingModule

    dynamic = TestingModule.configure()
    assert isinstance(dynamic, DynamicModule)
    assert dynamic.providers == []
    assert dynamic.exports == []
    assert dynamic.module is TestingModule


# ---------------------------------------------------------------------------
# Integration skip markers
# ---------------------------------------------------------------------------


def test_integration_markers_are_pytest_marks() -> None:
    from quadkit.testing.integration import markers

    assert len(markers.__all__) == 11
    for name in markers.__all__:
        mark = getattr(markers, name)
        assert mark is not None

    def dummy() -> None:
        """Dummy decorated function."""
        return None

    decorated = markers.requires_redis(dummy)
    assert any(
        m.name == "requires_redis" for m in getattr(decorated, "pytestmark", [])
    )


# ---------------------------------------------------------------------------
# Docstring-only scaffold modules (import guard)
# ---------------------------------------------------------------------------


def test_scaffold_modules_import() -> None:
    import importlib

    for module_name in (
        "quadkit.testing.decorators",
        "quadkit.testing.events",
        "quadkit.testing.hooks",
        "quadkit.testing.protocols",
        "quadkit.testing.di",
        "quadkit.testing.compliance",
        "quadkit.testing.fakes",
        "quadkit.testing.mocks",
        "quadkit.testing.websocket",
        "quadkit.testing.workflow",
        "quadkit.testing.lib",
        "quadkit.testing.integration",
    ):
        assert importlib.import_module(module_name) is not None


def test_compliance_module_exports_all_suites() -> None:
    from quadkit.testing import compliance

    expected = {
        "CacheBackendCompliance",
        "EventBusCompliance",
        "TaskQueueCompliance",
        "RepositoryCompliance",
        "WebhookDeliveryStoreCompliance",
        "StoreConformanceSuite",
    }
    assert expected <= set(compliance.__all__)
