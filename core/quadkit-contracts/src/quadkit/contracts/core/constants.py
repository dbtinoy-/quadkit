"""Entry-point group constants for Quadkit extensibility.

These constants define the standard entry-point groups used across the
Quadkit ecosystem for provider auto-discovery via ``importlib.metadata``.

Usage::

    from importlib.metadata import entry_points
    from quadkit.contracts.core.constants import EP_AI_SUBSYSTEMS

    for ep in entry_points(group=EP_AI_SUBSYSTEMS):
        provider_cls = ep.load()
        ...
"""

from __future__ import annotations

import importlib.metadata

try:
    __version__: str = importlib.metadata.version("quadkit-contracts")
except ImportError:
    __version__ = "0.0.0"


# ---------------------------------------------------------------------------
# Configuration Environment Variable Prefix
# ---------------------------------------------------------------------------

ENV_PREFIX: str = "QK_CONTRACTS__"
"""Environment variable prefix for contracts configuration (minimal usage)."""

# ---------------------------------------------------------------------------
# General provider / module discovery
# ---------------------------------------------------------------------------

EP_PROVIDERS = "quadkit.providers"
"""Auto-registering general-purpose providers."""

EP_MODULES = "quadkit.modules"
"""Core module auto-discovery."""

EP_MIDDLEWARE = "quadkit.middleware"
"""HTTP and event middleware auto-registration."""

# ---------------------------------------------------------------------------
# AI subsystem discovery
# ---------------------------------------------------------------------------

EP_AI_SUBSYSTEMS = "quadkit.ai.subsystems"
"""AI sub-package providers (LLM, Vector, RAG, Agents, Memory, etc.)."""

EP_AI_TOOLS = "quadkit.ai.tools"
"""AI tool and skill providers."""

EP_AI_STRATEGIES = "quadkit.ai.strategies"
"""Agent reasoning strategy implementations."""

EP_AI_GUARDS = "quadkit.ai.guards"
"""AI content safety guard implementations."""

EP_AI_BACKENDS_MEMORY = "quadkit.ai.backends.memory"
"""Pluggable memory storage backends."""

EP_AI_BACKENDS_EMBEDDING = "quadkit.ai.backends.embedding"
"""Pluggable embedding and chunking backends."""

# ---------------------------------------------------------------------------
# Plugin discovery
# ---------------------------------------------------------------------------

EP_PLUGINS = "quadkit.plugins"
"""Metadata-only plugin descriptors for admin-manageable enable/disable."""

# ---------------------------------------------------------------------------
# Infrastructure backend discovery
# ---------------------------------------------------------------------------

EP_CACHE_BACKENDS = "quadkit.cache.backends"
"""Cache backend implementations (Redis, Memcached, in-memory, etc.)."""

EP_DB_BACKENDS = "quadkit.sql.backends"
"""Database client implementations."""

EP_SEARCH_BACKENDS = "quadkit.search.backends"
"""Search engine backend implementations."""

EP_MESSAGING_BACKENDS = "quadkit.messaging.backends"
"""Message queue backend implementations."""

EP_MONITORING_BACKENDS = "quadkit.monitoring.backends"
"""Observability backend implementations."""

EP_TASKS_BACKENDS = "quadkit.tasks.backends"
"""Background task queue backend implementations."""

EP_STORAGE_BACKENDS = "quadkit.storage.backends"
"""Object storage backend implementations."""

# ---------------------------------------------------------------------------
# Strategy discovery
# ---------------------------------------------------------------------------

EP_CHUNKING_STRATEGIES = "quadkit.chunking.strategies"
"""RAG document chunking strategy implementations."""

EP_RETRIEVAL_STRATEGIES = "quadkit.retrieval.strategies"
"""RAG retrieval and ranking strategy implementations."""

EP_AGENT_STRATEGIES = "quadkit.agent.strategies"
"""Agent reasoning strategy implementations."""

EP_AUTH_STRATEGIES = "quadkit.auth.strategies"
"""Authentication method implementations."""

# ---------------------------------------------------------------------------
# Catalogue
# ---------------------------------------------------------------------------

ALL_ENTRY_POINT_GROUPS: dict[str, str] = {
    EP_PROVIDERS: "General-purpose auto-registering providers",
    EP_MODULES: "Core module auto-discovery",
    EP_MIDDLEWARE: "HTTP/event middleware auto-registration",
    EP_PLUGINS: "Metadata-only plugin descriptors",
    EP_AI_SUBSYSTEMS: "AI sub-package providers",
    EP_AI_TOOLS: "AI tools and skills",
    EP_AI_STRATEGIES: "Agent reasoning strategies",
    EP_AI_GUARDS: "Content safety guards",
    EP_AI_BACKENDS_MEMORY: "Memory storage backends",
    EP_AI_BACKENDS_EMBEDDING: "Embedding/chunking backends",
    EP_CACHE_BACKENDS: "Cache backend implementations",
    EP_DB_BACKENDS: "Database client implementations",
    EP_SEARCH_BACKENDS: "Search engine backends",
    EP_MESSAGING_BACKENDS: "Message queue backends",
    EP_MONITORING_BACKENDS: "Observability backends",
    EP_TASKS_BACKENDS: "Background task queue backends",
    EP_STORAGE_BACKENDS: "Object storage backends",
    EP_CHUNKING_STRATEGIES: "RAG chunking strategies",
    EP_RETRIEVAL_STRATEGIES: "RAG retrieval strategies",
    EP_AGENT_STRATEGIES: "Agent reasoning strategies",
    EP_AUTH_STRATEGIES: "Authentication strategies",
}

__all__ = [
    "ALL_ENTRY_POINT_GROUPS",
    "ENV_PREFIX",
    "EP_AGENT_STRATEGIES",
    "EP_AI_BACKENDS_EMBEDDING",
    "EP_AI_BACKENDS_MEMORY",
    "EP_AI_GUARDS",
    "EP_AI_STRATEGIES",
    "EP_AI_SUBSYSTEMS",
    "EP_AI_TOOLS",
    "EP_AUTH_STRATEGIES",
    "EP_CACHE_BACKENDS",
    "EP_CHUNKING_STRATEGIES",
    "EP_DB_BACKENDS",
    "EP_MESSAGING_BACKENDS",
    "EP_MIDDLEWARE",
    "EP_MODULES",
    "EP_MONITORING_BACKENDS",
    "EP_PLUGINS",
    "EP_PROVIDERS",
    "EP_RETRIEVAL_STRATEGIES",
    "EP_SEARCH_BACKENDS",
    "EP_STORAGE_BACKENDS",
    "EP_TASKS_BACKENDS",
    "__version__",
]
