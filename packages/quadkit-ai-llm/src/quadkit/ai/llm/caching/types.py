"""Types and models for LLM caching."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from quadkit.ai.llm.protocols import LLMCacheProtocol
from quadkit.domain import DomainModel
from quadkit.security.hashing import ambient as hashing
from quadkit.validation import Field

__all__ = [
    "CacheEntry",
    "CacheStats",
    "LLMCacheProtocol",
    "build_llm_cache_key",
]


@dataclass(init=False)
class CacheEntry(DomainModel):
    """Cache entry with metadata.

    Attributes:
        key: Cache key.
        value: Cached value.
        created_at: When entry was created.
        last_access_at: When the entry was last read (LRU eviction order).
        expires_at: When entry expires (Unix timestamp).
        hits: Number of cache hits.
        size_bytes: Approximate size in bytes.
    """

    key: str = Field(..., description="Cache key")
    value: Any = Field(..., description="Cached value")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Creation timestamp",
    )
    last_access_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Last access timestamp (LRU eviction order)",
    )
    expires_at: float = Field(..., description="Expiration timestamp (Unix)")
    hits: int = Field(default=0, description="Number of hits")
    size_bytes: int = Field(default=0, description="Approximate size in bytes")


@dataclass(init=False)
class CacheStats(DomainModel):
    """Cache statistics.

    Attributes:
        hits: Number of cache hits.
        misses: Number of cache misses.
        evictions: Number of evictions.
        total_entries: Current number of entries.
        total_size_bytes: Total cache size in bytes.
    """

    hits: int = Field(default=0, description="Cache hits")
    misses: int = Field(default=0, description="Cache misses")
    evictions: int = Field(default=0, description="Cache evictions")
    total_entries: int = Field(default=0, description="Total entries")
    total_size_bytes: int = Field(default=0, description="Total size in bytes")

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0


def build_llm_cache_key(
    provider: str,
    model: str,
    prompt: str,
    model_revision: str | None = None,
    prompt_hash: bytes | None = None,
) -> str:
    """Build a deterministic cache key for LLM responses.

    Includes ``model_revision`` and ``prompt_hash`` when available so that
    different revisions or prompts produce distinct cache entries.

    Args:
        provider: Provider name (e.g. ``"openai"``).
        model: Model name (e.g. ``"gpt-4"``).
        prompt: The raw prompt text.
        model_revision: Optional model revision string.
        prompt_hash: Optional SHA-256 hash of the prompt.

    Returns:
        A hex-encoded SHA-256 cache key.
    """
    key_parts: list[str] = [provider, model, prompt]
    if model_revision:
        key_parts.append(model_revision)
    if prompt_hash:
        key_parts.append(prompt_hash.hex())
    return hashing.hash_hex("|".join(key_parts))
