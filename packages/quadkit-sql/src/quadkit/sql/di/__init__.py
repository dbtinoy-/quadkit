"""Integration helpers for quadkit-sql.

Use :class:`~quadkit.sql.config.DatabaseConfig` directly — it auto-loads
from ``QK_DB__*`` environment variables via Pydantic's ``model_config``.
"""

from __future__ import annotations

from quadkit.sql.di.provider import DatabaseProvider
from quadkit.sql.module import DatabaseModule

__all__ = ["DatabaseModule", "DatabaseProvider"]
