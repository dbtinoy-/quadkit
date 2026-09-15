"""Lazy-loader for optional AI fixtures submodule."""

from __future__ import annotations

import types

_ai_module: types.ModuleType | None = None

_AI_FIXTURE_NAMES = frozenset(
    {
        "intelligence_assertions",
        "intelligence_test_bed",
        "intelligence_test_client",
        "intelligence_test_data",
        "llm_client",
        "ml_predictor",
        "mock_llm_client",
        "mock_ml_predictor",
        "mock_vector_store",
        "populated_vector_store",
        "sample_chat_messages",
        "sample_documents",
        "sample_features",
        "sample_llm_responses",
        "sample_predictions",
        "vector_store",
    }
)


def get_ai_fixture(name: str) -> object:
    """Return the named AI fixture, lazily importing the ai submodule."""
    global _ai_module
    if _ai_module is None:
        from quadkit.testing.fixtures import ai as _ai_module
    return getattr(_ai_module, name)


def is_ai_fixture(name: str) -> bool:
    return name in _AI_FIXTURE_NAMES
