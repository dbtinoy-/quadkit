"""Pytest fixtures for Quadkit Framework testing.

The core fixtures are imported eagerly — they depend only on packages that
always ship. The DB, task, web and AI fixtures live in modules that ship with
their optional extras, so those names are declared in a lazy table and resolved
on first access; accessing one without its extra raises `AttributeError`, and
`__all__` keeps the public contract truthful in every projection.
"""

from __future__ import annotations

from typing import Any, Final

from quadkit.testing._lazy_exports import resolve_export
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

_LAZY_IMPORTS: Final[dict[str, tuple[str, str]]] = {
    # the database extra
    "clean_database": ("quadkit.testing.fixtures.db", "clean_database"),
    "database_provider": ("quadkit.testing.fixtures.db", "database_provider"),
    "db_test_bed": ("quadkit.testing.fixtures.db", "db_test_bed"),
    "db_transaction": ("quadkit.testing.fixtures.db", "db_transaction"),
    "mock_connection": ("quadkit.testing.fixtures.db", "mock_connection"),
    "mock_connection_pool": ("quadkit.testing.fixtures.db", "mock_connection_pool"),
    "sample_order_data": ("quadkit.testing.fixtures.db", "sample_order_data"),
    "sample_product_data": ("quadkit.testing.fixtures.db", "sample_product_data"),
    "sample_user_data": ("quadkit.testing.fixtures.db", "sample_user_data"),
    "seeded_database": ("quadkit.testing.fixtures.db", "seeded_database"),
    "test_database_client": ("quadkit.testing.fixtures.db", "test_database_client"),
    # the tasks extra
    "sample_task_data": ("quadkit.testing.fixtures.tasks", "sample_task_data"),
    "task_test_bed": ("quadkit.testing.fixtures.tasks", "task_test_bed"),
    "task_test_client": ("quadkit.testing.fixtures.tasks", "task_test_client"),
    # the web extra
    "app_bed": ("quadkit.testing.fixtures.web", "app_bed"),
    "authenticated_web_client": (
        "quadkit.testing.fixtures.web",
        "authenticated_web_client",
    ),
    "mock_web_request": ("quadkit.testing.fixtures.web", "mock_web_request"),
    "mock_web_response": ("quadkit.testing.fixtures.web", "mock_web_response"),
    "sample_web_post_data": ("quadkit.testing.fixtures.web", "sample_web_post_data"),
    "sample_web_user_data": ("quadkit.testing.fixtures.web", "sample_web_user_data"),
    "web_test_bed": ("quadkit.testing.fixtures.web", "web_test_bed"),
    "web_test_client": ("quadkit.testing.fixtures.web", "web_test_client"),
    # the AI extra
    "intelligence_assertions": (
        "quadkit.testing.fixtures.ai",
        "intelligence_assertions",
    ),
    "intelligence_test_bed": ("quadkit.testing.fixtures.ai", "intelligence_test_bed"),
    "intelligence_test_client": (
        "quadkit.testing.fixtures.ai",
        "intelligence_test_client",
    ),
    "intelligence_test_data": ("quadkit.testing.fixtures.ai", "intelligence_test_data"),
    "llm_client": ("quadkit.testing.fixtures.ai", "llm_client"),
    "ml_predictor": ("quadkit.testing.fixtures.ai", "ml_predictor"),
    "mock_llm_client": ("quadkit.testing.fixtures.ai", "mock_llm_client"),
    "mock_ml_predictor": ("quadkit.testing.fixtures.ai", "mock_ml_predictor"),
    "mock_vector_store": ("quadkit.testing.fixtures.ai", "mock_vector_store"),
    "populated_vector_store": ("quadkit.testing.fixtures.ai", "populated_vector_store"),
    "sample_chat_messages": ("quadkit.testing.fixtures.ai", "sample_chat_messages"),
    "sample_documents": ("quadkit.testing.fixtures.ai", "sample_documents"),
    "sample_features": ("quadkit.testing.fixtures.ai", "sample_features"),
    "sample_llm_responses": ("quadkit.testing.fixtures.ai", "sample_llm_responses"),
    "sample_predictions": ("quadkit.testing.fixtures.ai", "sample_predictions"),
    "vector_store": ("quadkit.testing.fixtures.ai", "vector_store"),
}

# Modules that ship only with their optional extra.
_OPTIONAL_MODULES: Final[frozenset[str]] = frozenset(
    {
        "quadkit.testing.fixtures.db",
        "quadkit.testing.fixtures.tasks",
        "quadkit.testing.fixtures.web",
        "quadkit.testing.fixtures.ai",
    }
)


def __getattr__(name: str) -> Any:
    """Import and return a public attribute on first access."""
    return resolve_export(
        name,
        _LAZY_IMPORTS,
        package=__name__,
        optional=_OPTIONAL_MODULES,
    )


def __dir__() -> list[str]:
    """Return the importable public names."""
    return sorted(__all__)


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
