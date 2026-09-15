"""Shared AI chunk types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Chunk:
    """Canonical AI chunk shared by RAG-oriented packages."""

    text: str
    source: str = "unknown"
    metadata: dict[str, Any] = field(default_factory=dict)
    score: float | None = None
    embedding: list[float] | None = None


@dataclass(frozen=True)
class ContextChunk(Chunk):
    """Retrieved chunk enriched with ranking metadata."""

    rank: int = 0


__all__ = ["Chunk", "ContextChunk"]
