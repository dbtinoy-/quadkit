"""Convention followed: **Yaml-first config** — typed ``BaseConfig`` dataclass
bound to a named yaml section; ``QK_<SECTION>__KEY`` env overrides apply.

Typed configuration for the LLM Structured Output demo.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from quadkit.config import BaseConfig
from quadkit.contracts.core.config import Environment
from quadkit.validation import ConfigDict, Field


@dataclass(init=False)
class LlmSideConfig(BaseConfig):
    """Demo-owned settings for structured extraction and response caching."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")
    config_section: ClassVar[str] = "llm_side"
    name: str = "llm_side"
    enabled: bool = True
    env: Environment | None = Field(None, description="Deployment environment")
    model: str = Field(
        default="demo-extractor-v1",
        description="Model identifier used for structured extraction and cost estimation",
    )
    cache_ttl: float = Field(
        default=300.0,
        description="Seconds an extracted structured response stays cached in LLMCache",
    )


__all__ = ["LlmSideConfig"]
