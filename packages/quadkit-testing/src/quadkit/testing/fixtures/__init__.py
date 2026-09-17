"""Pytest fixtures for Quadkit Framework testing."""

from __future__ import annotations

import importlib.util

from quadkit.testing.fixtures._lazy import get_ai_fixture, is_ai_fixture
from quadkit.testing.fixtures.core import (
    ContainerTestFixture,
    assertions,
    fake_cache,
    fake_clock,
    fake_command_bus,
    fake_config,
    fake_event_bus,
    fake_logger,
    fake_metrics,
    fake_query_bus,
    fake_state_store,
    fake_unit_of_work,
    test_bed,
    test_container,
    test_data,
)

try:
    from quadkit.testing.fixtures.db import (
        clean_database,
        database_provider,
        db_test_bed,
        db_transaction,
        mock_connection,
        mock_connection_pool,
        sample_order_data,
        sample_product_data,
        sample_user_data,
        seeded_database,
        test_database_client,
    )

    _db_available = True
except ImportError:
    _db_available = False

try:
    from quadkit.testing.fixtures.tasks import (
        sample_task_data,
        task_test_bed,
        task_test_client,
    )

    _tasks_available = True
except ImportError:
    _tasks_available = False
try:
    from quadkit.testing.fixtures.web import (
        app_bed,
        authenticated_web_client,
        mock_web_request,
        mock_web_response,
        sample_web_post_data,
        sample_web_user_data,
        web_test_bed,
        web_test_client,
    )

    _web_available = True
except ImportError:
    _web_available = False


def __getattr__(name: str) -> object:
    if is_ai_fixture(name) and _OPTIONAL_AI_AVAILABLE:
        try:
            return get_ai_fixture(name)
        except (ImportError, AttributeError) as e:
            raise AttributeError(
                f"module {__name__!r} has no attribute {name!r}"
            ) from e
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


_OPTIONAL_AI_AVAILABLE = importlib.util.find_spec(f"{__name__}.ai") is not None


__all__ = [
    # Container fixtures
    "ContainerTestFixture",
    "app_bed",
    # Core fixtures
    "assertions",
    # Web fixtures
    "authenticated_web_client",
    # DB fixtures
    "clean_database",
    "database_provider",
    "db_test_bed",
    "db_transaction",
    # Fake service fixtures
    "fake_cache",
    "fake_clock",
    "fake_command_bus",
    "fake_config",
    "fake_event_bus",
    "fake_logger",
    "fake_metrics",
    "fake_query_bus",
    "fake_state_store",
    "fake_unit_of_work",
    # AI fixtures
    "intelligence_assertions",
    "intelligence_test_bed",
    "intelligence_test_client",
    "intelligence_test_data",
    "llm_client",
    "ml_predictor",
    "mock_connection",
    "mock_connection_pool",
    "mock_llm_client",
    "mock_ml_predictor",
    "mock_vector_store",
    "mock_web_request",
    "mock_web_response",
    "populated_vector_store",
    "sample_chat_messages",
    "sample_documents",
    "sample_features",
    "sample_llm_responses",
    "sample_order_data",
    "sample_predictions",
    "sample_product_data",
    "sample_user_data",
    "sample_web_post_data",
    "sample_web_user_data",
    "seeded_database",
    "test_bed",
    "test_container",
    "test_data",
    "test_database_client",
    "vector_store",
    "web_test_bed",
    "web_test_client",
]

# Keep the public export contract truthful when optional fixture modules are
# omitted by the exporter. Names provided by an available module remain lazy;
# names from absent modules are not advertised or resolved by __getattr__.
__all__ = [
    name
    for name in __all__
    if name in globals() or (is_ai_fixture(name) and _OPTIONAL_AI_AVAILABLE)
]
