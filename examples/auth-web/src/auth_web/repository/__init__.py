"""Storage adapters for the auth web demo."""

from __future__ import annotations

from auth_web.repository.session_repository import InMemorySessionRepository

__all__ = ["InMemorySessionRepository"]
