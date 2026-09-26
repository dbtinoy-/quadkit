"""Convention followed: **Yaml-first config** — typed ``BaseConfig`` dataclass
bound to a named yaml section; ``QK_<SECTION>__KEY`` env overrides apply.

Typed configuration for the HTTP Client demo.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from quadkit.config import BaseConfig
from quadkit.contracts.core.config import Environment
from quadkit.validation import ConfigDict, Field


@dataclass(init=False)
class HttpSideConfig(BaseConfig):
    """Demo-owned settings; the HTTP client itself belongs to ``quadkit-http``.

    The demo boots a small in-process ``aiohttp`` upstream (never a real
    third party) on a loopback host; ``upstream_host`` is the only knob.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")
    config_section: ClassVar[str] = "http_side"
    name: str = "http_side"
    enabled: bool = True
    env: Environment | None = Field(None, description="Deployment environment")
    upstream_host: str = Field(
        default="127.0.0.1",
        description="Loopback host the in-process mock upstream binds to",
    )


__all__ = ["HttpSideConfig"]
