"""Convention followed: **Yaml-first config** — typed ``BaseConfig`` dataclass
bound to a named yaml section; ``QK_<SECTION>__KEY`` env overrides apply.

Typed configuration for the Minimal API demo.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from quadkit.config import BaseConfig
from quadkit.contracts.core.config import Environment
from quadkit.validation import ConfigDict, Field


@dataclass(init=False)
class MinimalApiConfig(BaseConfig):
    """Demo-owned settings; the web server itself belongs to ``web:``.

    The demo is deliberately tiny — one knob (the greeting) proves the
    config wiring end to end: yaml default, typed validation, env override
    (``QK_MINIMAL_API__GREETING``), and health reporting.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")
    config_section: ClassVar[str] = "minimal_api"
    name: str = "minimal_api"
    enabled: bool = True
    env: Environment | None = Field(None, description="Deployment environment")
    greeting: str = Field(
        default="hello, quadkit",
        description="Greeting returned by GET /hello",
    )


__all__ = ["MinimalApiConfig"]
