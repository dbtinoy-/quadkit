"""Convention followed: **Yaml-first config** — typed ``BaseConfig`` dataclass bound to a named yaml section; ``QK_<SECTION>__KEY`` env overrides apply.

Typed configuration for the event-driven-orders demo.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from quadkit.config import BaseConfig
from quadkit.contracts.core.config import Environment
from quadkit.validation import ConfigDict, Field


@dataclass(init=False)
class OrdersConfig(BaseConfig):
    """Demo-owned display metadata; framework modules own their sections."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")
    config_section: ClassVar[str] = "orders"
    name: str = "orders"
    enabled: bool = True
    env: Environment | None = Field(None, description="Deployment environment")
    service_name: str = Field(
        default="orders demo",
        description="Service label shown in demo health output",
    )


__all__ = ["OrdersConfig"]
