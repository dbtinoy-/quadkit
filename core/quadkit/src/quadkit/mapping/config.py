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
        description=(
            "Fall back to auto-mapping in map_or_auto() when no explicit mapper "
            "is registered."
        ),
    )
    ignore_unknown: bool = Field(
        default=True,
        description=(
            "Drop source fields the destination does not declare. Set False to "
            "raise MappingExecutionError instead, so a shape mismatch on either "
            "side of the mapping fails loudly."
        ),
    )
    case_sensitive: bool = Field(
        default=True,
        description=(
            "Match source keys to destination fields case-sensitively. Set "
            "False to match `Name` to `name`."
        ),
    )


__all__ = ["MappingConfig"]
