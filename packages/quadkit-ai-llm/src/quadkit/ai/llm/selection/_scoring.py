"""Selector factory presets for model scoring tradeoffs."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from quadkit.ai.llm.selection.core import ModelSelector


def create_cost_optimized_selector(
    budget_per_1k_tokens: float = 2.0,
) -> ModelSelector:
    """Create a cost-optimized model selector."""
    from quadkit.ai.llm.selection.core import ModelSelector, SelectionStrategy

    _ = budget_per_1k_tokens
    strategies = [
        SelectionStrategy(
            name="budget_tiny",
            model="claude-3-haiku-20240307",
            conditions={"max_tokens": 500},
            priority=10,
            description=None,
        ),
        SelectionStrategy(
            name="budget_small",
            model="gpt-3.5-turbo",
            conditions={"max_tokens": 2000},
            priority=9,
            description=None,
        ),
        SelectionStrategy(
            name="budget_medium",
            model="claude-3-sonnet-20240229",
            conditions={"max_tokens": 10000},
            priority=8,
            description=None,
        ),
    ]

    return ModelSelector(
        default_model="gpt-3.5-turbo",
        strategies=strategies,
        fallback_chain=[
            "claude-3-haiku-20240307",
            "gpt-3.5-turbo",
            "ollama/llama3",
        ],
    )


def create_quality_optimized_selector() -> ModelSelector:
    """Create a quality-optimized model selector."""
    from quadkit.ai.llm.selection.core import ModelSelector, SelectionStrategy

    strategies = [
        SelectionStrategy(
            name="max_quality_long",
            model="claude-3-opus-20240229",
            conditions={"min_tokens": 1000},
            priority=10,
            description=None,
        ),
        SelectionStrategy(
            name="max_quality_short",
            model="gpt-4-turbo",
            conditions={"max_tokens": 10000},
            priority=9,
            description=None,
        ),
    ]

    return ModelSelector(
        default_model="gpt-4-turbo",
        strategies=strategies,
        fallback_chain=[
            "claude-3-opus-20240229",
            "gpt-4-turbo",
            "claude-3-sonnet-20240229",
            "gpt-3.5-turbo",
        ],
    )


def create_balanced_selector() -> ModelSelector:
    """Create a balanced model selector."""
    from quadkit.ai.llm.selection.core import ModelSelector, SelectionStrategy

    strategies = [
        SelectionStrategy(
            name="simple_fast",
            model="claude-3-haiku-20240307",
            conditions={"max_tokens": 500},
            priority=10,
            description=None,
        ),
        SelectionStrategy(
            name="medium_balanced",
            model="claude-3-sonnet-20240229",
            conditions={"min_tokens": 500, "max_tokens": 5000},
            priority=9,
            description=None,
        ),
        SelectionStrategy(
            name="complex_quality",
            model="gpt-4-turbo",
            conditions={"min_tokens": 5000},
            priority=8,
            description=None,
        ),
    ]

    return ModelSelector(
        default_model="claude-3-sonnet-20240229",
        strategies=strategies,
        fallback_chain=[
            "claude-3-sonnet-20240229",
            "gpt-3.5-turbo",
            "claude-3-haiku-20240307",
        ],
    )
