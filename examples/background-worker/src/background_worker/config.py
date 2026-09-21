"""Convention followed: **Yaml-first config** — typed ``BaseConfig`` dataclass
bound to a named yaml section; ``QK_<SECTION>__KEY`` env overrides apply.

Typed configuration for the Background Worker demo.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from quadkit.config import BaseConfig
from quadkit.contracts.core.config import Environment
from quadkit.validation import ConfigDict, Field


@dataclass(init=False)
class BackgroundWorkerConfig(BaseConfig):
    """Demo-owned settings; the web server itself belongs to ``web:``.

    ``concurrency`` is the bounded pool size — the production lever you
    would tune per deployment instead of editing code.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")
    config_section: ClassVar[str] = "background_worker"
    name: str = "background_worker"
    enabled: bool = True
    env: Environment | None = Field(None, description="Deployment environment")
    concurrency: int = Field(
        default=2,
        description="Worker coroutines consuming the queue concurrently",
    )
    poll_timeout: float = Field(
        default=0.05,
        description="Seconds each worker waits for the next task before re-polling",
    )


__all__ = ["BackgroundWorkerConfig"]
