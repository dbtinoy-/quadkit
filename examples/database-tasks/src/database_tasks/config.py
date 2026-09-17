"""Convention followed: **Yaml-first config** — typed ``BaseConfig`` dataclass
bound to a named yaml section; ``QK_<SECTION>__KEY`` env overrides apply.

Typed configuration for the Database Tasks demo.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from quadkit.config import BaseConfig
from quadkit.contracts.core.config import Environment
from quadkit.validation import ConfigDict, Field


@dataclass(init=False)
class DatabaseTasksConfig(BaseConfig):
    """Demo-owned settings; the web server itself belongs to ``web:``.

    ``db_path`` defaults to the in-memory SQLite database so the template
    runs with zero setup; point it at a file path for persistence across
    restarts (``QK_DATABASE_TASKS__DB_PATH=/var/lib/demo/tasks.db``).
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")
    config_section: ClassVar[str] = "database_tasks"
    name: str = "database_tasks"
    enabled: bool = True
    env: Environment | None = Field(None, description="Deployment environment")
    db_path: str = Field(
        default=":memory:",
        description="SQLite database path; ':memory:' for the in-memory database",
    )


__all__ = ["DatabaseTasksConfig"]
