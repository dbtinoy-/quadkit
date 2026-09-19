"""Configuration models for the mapping subsystem.

Contains :class:`MappingConfig`, which controls mapper strictness and
auto-mapping fallback behaviour.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from quadkit.config.base import BaseConfig
from quadkit.validation import ConfigDict, Field


@dataclass(init=False)
class MappingConfig(BaseConfig):
    """Object-to-object mapper configuration."""

    model_config: ClassVar[ConfigDict] = ConfigDict(
        extra="ignore",
    )

    strict: bool = Field(
        default=False,
        description="Raise on missing fields during mapping when True.",
    )
    auto_map: bool = Field(
        default=True,
        description="Fall back to auto-mapping when no explicit mapper is registered.",
    )


__all__ = ["MappingConfig"]
