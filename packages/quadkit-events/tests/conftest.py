# tests/conftest.py
import os
import sys
from pathlib import Path
from types import ModuleType

import pytest

# Direct sibling-helper imports (e.g. ``bus_test_support``) resolve through
# this fronted path because pytest's importlib mode does not put test
# directories on sys.path and ``tests/unit`` has no ``__init__.py``.
_UNIT_TESTS_DIR = Path(__file__).resolve().parent / "unit"
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

# Resolve dependencies via uv workspace
from quadkit.logging import get_logger

logger = get_logger(__name__)

# Annotate as ModuleType | None to avoid mypy assignment errors when import fails
pytest_asyncio: ModuleType | None = None
try:
    import pytest_asyncio
except ImportError:
    # Leave as None when unavailable
    pytest_asyncio = None

# Load core testing fixtures
try:
    import importlib

    importlib.import_module("quadkit.testing.fixtures.core")
except ImportError:
    pass

# Load integration fixtures for infrastructure services

# Ensure optional external dependencies used in tests are present as minimal
# stubs so tests can patch their members without requiring installation.
try:
    import importlib

    importlib.import_module("azure.servicebus")
except ImportError:
    import types
    from unittest.mock import AsyncMock

    # Create minimal servicebus modules and classes to enable patching in tests
    svc_mod = types.ModuleType("azure.servicebus")
    aio_mod = types.ModuleType("azure.servicebus.aio")

    class ServiceBusClient:
        @classmethod
        def from_connection_string(cls, conn):
            return cls()

        async def get_topic_sender(self, topic_name):
            return AsyncMock()

        async def get_subscription_receiver(
            self, topic_name, subscription_name, prefetch_count,
        ):
            return AsyncMock()

        async def close(self):
            return None

    class ServiceBusMessage:
        def __init__(self, *args, **kwargs):
            pass

    setattr(aio_mod, "ServiceBusClient", ServiceBusClient)
    setattr(svc_mod, "ServiceBusMessage", ServiceBusMessage)

    import sys

    sys.modules["azure.servicebus"] = svc_mod
    sys.modules["azure.servicebus.aio"] = aio_mod

    if "azure" not in sys.modules:
        sys.modules["azure"] = types.ModuleType("azure")
    setattr(sys.modules["azure"], "servicebus", svc_mod)



# The quadkit.testing package is optional in this workspace and may
# be partially broken when running isolated unit tests.  Importing it
# should not abort the entire test run, so we guard the import and
# provide a simple fallback implementation used by our fixtures.
try:
    from quadkit.testing import TestEnvironment
except ImportError:  # pragma: no cover - fallback used only in minimal environments
    class TestEnvironment:
        """Minimal stub used when the real testing package is unavailable."""

        class _DummyCtx:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

        def __init__(self) -> None:
            pass

        def context(self):
            return self._DummyCtx()



@ pytest.fixture if pytest_asyncio is None else pytest_asyncio.fixture
async def test_bed():
    """Async TestBed fixture for testing."""
    bed = TestEnvironment()
    async with bed.context():
        yield bed


# Convenience helper for constructing DomainEvent instances in tests
# to avoid repetitive required-field noise in tests and satisfy static
# type-checking.
def make_domain_event(**kwargs):
    from uuid import uuid4

    from quadkit.contracts.domain import DomainEvent

    data = {
        "aggregate_id": kwargs.get("aggregate_id", uuid4()),
        "aggregate_type": kwargs.get("aggregate_type", "TestAggregate"),
        # DomainEvent no longer accepts version directly in __init__
        "event_type": kwargs.get("event_type", None),
        "sequence_number": kwargs.get("sequence_number", kwargs.get("version", 0)),
        "actor_id": kwargs.get("actor_id", None),
    }
    data.update(kwargs)
    if "version" in data:
        del data["version"]
    return DomainEvent(**data)


# Generic helpers for building typed messages used throughout tests.
# These avoid repeated named-argument noise when instantiating subclasses
# of DomainEvent, Command, and Query in tests.


def _make_model(cls, **kwargs):
    from uuid import uuid4

    data = {
        "aggregate_id": kwargs.get("aggregate_id", uuid4()),
        "aggregate_type": kwargs.get("aggregate_type", "TestAggregate"),
        # version no longer part of base DomainEvent directly in __init__
        "event_type": kwargs.get("event_type", None),
        "sequence_number": kwargs.get("sequence_number", kwargs.get("version", 0)),
        "actor_id": kwargs.get("actor_id", None),
    }
    data.update(kwargs)
    if "version" in data:
        del data["version"]
    return cls(**data)


def make_event(event_cls, **kwargs):
    """Create an event instance of `event_cls` with sensible defaults."""
    return _make_model(event_cls, **kwargs)


def make_command(command_cls, **kwargs):
    """Create a command instance with sensible defaults."""
    defaults = {
        "target_aggregate_id": kwargs.get("target_aggregate_id"),
        "expected_version": kwargs.get("expected_version", None),
    }
    defaults.update(kwargs)
    return command_cls(**defaults)


def make_query(query_cls, **kwargs):
    """Create a query instance with sensible defaults."""
    return query_cls(**kwargs)
