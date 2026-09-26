"""Convention followed: **Yaml-first config** — typed ``BaseConfig`` dataclass bound to a named yaml section; ``QK_<SECTION>__KEY`` env overrides apply.

Typed configuration for the auth-apikeys demo.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from quadkit.config import BaseConfig
from quadkit.contracts.core.config import Environment
from quadkit.validation import ConfigDict, Field


@dataclass(init=False)
class ApikeyConsoleConfig(BaseConfig):
    """Demo-owned display metadata; framework modules own their sections."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")
    config_section: ClassVar[str] = "apikey_console"
    name: str = "apikey_console"
    enabled: bool = True
    env: Environment | None = Field(None, description="Deployment environment")
    service_name: str = Field(
        default="apikey console",
        description="Service label shown in demo health output",
    )


__all__ = ["ApikeyConsoleConfig"]
