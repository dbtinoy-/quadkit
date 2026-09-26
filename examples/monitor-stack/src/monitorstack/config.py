"""Convention followed: **Yaml-first config** — typed ``BaseConfig`` dataclass bound to a named yaml section; ``QK_<SECTION>__KEY`` env overrides apply.

Typed configuration for the monitor console."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from quadkit.config import BaseConfig
from quadkit.contracts.core.config import Environment
from quadkit.validation import ConfigDict, Field


@dataclass(init=False)
class MonitorStackConfig(BaseConfig):
    """Demo-owned display metadata; MonitorModule owns observability config."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")
    config_section: ClassVar[str] = "monitorstack"
    name: str = "monitorstack"
    enabled: bool = True
    env: Environment | None = Field(None, description="Deployment environment")
    service_name: str = Field(
        default="monitor-console",
        description="Service label shown in the demo health response",
    )


__all__ = ["MonitorStackConfig"]
