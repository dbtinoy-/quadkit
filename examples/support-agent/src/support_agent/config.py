"""Convention followed: **Yaml-first config** — typed ``BaseConfig`` dataclass bound to a named yaml section; ``QK_<SECTION>__KEY`` env overrides apply.

Typed configuration for the support-agent demo.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from quadkit.config import BaseConfig
from quadkit.contracts.core.config import Environment
from quadkit.validation import ConfigDict, Field


@dataclass(init=False)
class SupportAgentConfig(BaseConfig):
    """Demo-owned display metadata; framework modules own their sections."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")
    config_section: ClassVar[str] = "support_agent"
    name: str = "support_agent"
    enabled: bool = True
    env: Environment | None = Field(None, description="Deployment environment")
    service_name: str = Field(
        default="support agent",
        description="Service label shown in demo health output",
    )


__all__ = ["SupportAgentConfig"]
