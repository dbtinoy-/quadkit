"""Convention followed: **Yaml-first config** — typed ``BaseConfig`` dataclass bound to a named yaml section; ``QK_<SECTION>__KEY`` env overrides apply.

Typed configuration for the SQL repository demo."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from quadkit.config import BaseConfig
from quadkit.contracts.core.config import Environment
from quadkit.validation import ConfigDict, Field


@dataclass(init=False)
class TaskAppConfig(BaseConfig):
    """Small demo-owned config section kept separate from SQL config."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")
    config_section: ClassVar[str] = "task_app"
    name: str = "task_app"
    enabled: bool = True
    env: Environment | None = Field(None, description="Deployment environment")
    project_name: str = Field(
        default="SQL Task Repository",
        description="Display name for this standalone demo",
    )


__all__ = ["TaskAppConfig"]
