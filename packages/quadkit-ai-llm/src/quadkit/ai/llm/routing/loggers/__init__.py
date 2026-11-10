"""Inference logger implementations for LLM routing."""

from __future__ import annotations

from quadkit.ai.llm.routing.loggers.database import DatabaseInferenceLogger
from quadkit.ai.llm.routing.loggers.memory import InMemoryInferenceLogger

__all__ = [
    "DatabaseInferenceLogger",
    "InMemoryInferenceLogger",
]
