"""Convention followed: **Yaml-first config** — typed ``BaseConfig`` dataclass bound to a named yaml section; ``QK_<SECTION>__KEY`` env overrides apply.

Demo-only configuration for the Events Timeline / Replay Lab."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from quadkit.config.base import BaseConfig
from quadkit.validation import ConfigDict, Field


@dataclass(init=False)
class TimelineLabConfig(BaseConfig):
    """Small scenario configuration; event behavior remains package-owned."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    config_section: ClassVar[str] = "timeline_lab"

    enabled: bool = True
    stream_id: str = Field("checkout-demo", min_length=1)
    default_actor: str = Field("browser-operator", min_length=1)


__all__ = ["TimelineLabConfig"]
