"""Convention followed: **Yaml-first config** — typed ``BaseConfig`` dataclass
bound to a named yaml section; ``QK_<SECTION>__KEY`` env overrides apply.

Typed configuration for the Task Console demo.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from quadkit.config import BaseConfig
from quadkit.contracts.core.config import Environment
from quadkit.validation import ConfigDict, Field


@dataclass(init=False)
class TaskConsoleConfig(BaseConfig):
    """Demo-owned display settings; job queueing/scheduling belongs to Quadkit."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")
    config_section: ClassVar[str] = "task_console"
    name: str = "task_console"
    enabled: bool = True
    env: Environment | None = Field(None, description="Deployment environment")
    seed_demo_jobs: bool = Field(
        default=True,
        description="Enqueue a few sample jobs on boot, including one that always fails",
    )
    poll_wait_seconds: float = Field(
        default=3.0,
        description="Max seconds the /jobs/{id} endpoint waits for a job result before returning pending",
    )


__all__ = ["TaskConsoleConfig"]
