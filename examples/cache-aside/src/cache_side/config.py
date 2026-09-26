"""Convention followed: **Yaml-first config** — typed ``BaseConfig`` dataclass
bound to a named yaml section; ``QK_<SECTION>__KEY`` env overrides apply.

Typed configuration for the Cache-Aside demo.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from quadkit.config import BaseConfig
from quadkit.contracts.core.config import Environment
from quadkit.validation import ConfigDict, Field


@dataclass(init=False)
class CacheSideConfig(BaseConfig):
    """Demo-owned settings; cache backend behavior belongs to ``quadkit-cache``.

    The demo is deliberately tiny — one knob (``report_ttl``) proves the
    cache-aside wiring end to end: a computed report is stored for this many
    seconds and served from the cache until it expires or is invalidated.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")
    config_section: ClassVar[str] = "cache_side"
    name: str = "cache_side"
    enabled: bool = True
    env: Environment | None = Field(None, description="Deployment environment")
    report_ttl: int = Field(
        default=60,
        description="Seconds a computed report stays cached before recompute",
    )


__all__ = ["CacheSideConfig"]
