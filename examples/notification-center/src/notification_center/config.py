"""Convention followed: **Yaml-first config** — typed ``BaseConfig`` dataclass
bound to a named yaml section; ``QK_<SECTION>__KEY`` env overrides apply.

Typed configuration for the Notification Center demo.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from quadkit.config import BaseConfig
from quadkit.contracts.core.config import Environment
from quadkit.validation import ConfigDict, Field


@dataclass(init=False)
class NotificationCenterConfig(BaseConfig):
    """Demo-owned display settings; email/inbox delivery belongs to Quadkit."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")
    config_section: ClassVar[str] = "notification_center"
    name: str = "notification_center"
    enabled: bool = True
    env: Environment | None = Field(None, description="Deployment environment")
    seed_demo_inbox: bool = Field(
        default=True,
        description="Seed a few sample inbox messages on boot so the console has data to browse",
    )
    default_user_id: str = Field(
        default="demo-user",
        description="User ID pre-filled in the browser's inbox panel",
    )


__all__ = ["NotificationCenterConfig"]
