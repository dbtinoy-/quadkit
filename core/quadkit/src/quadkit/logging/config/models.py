"""Configuration model for the logging subsystem."""

from __future__ import annotations

from dataclasses import dataclass

from quadkit.config import BaseConfig
from quadkit.logging.config.redaction import RedactionConfig
from quadkit.logging.config.sampling import SamplingConfig
from quadkit.validation import Field, model_validator


@dataclass(init=False)
class LoggingConfig(BaseConfig):
    """Logging configuration.

    Attributes:
        level: Global minimum log level.
        json_format: Whether to render logs as JSON.
        levels: Per-logger level overrides keyed by logger name prefix.
            Example: ``{"quadkit.di": "DEBUG", "quadkit.web": "WARNING"}``.
        sampling: Optional sampling configuration for rate-limiting
            high-volume log events in production.
        redaction: Optional configuration for log event field redaction.
    """

    level: str = Field(default="INFO", description="Global log level")
    json_format: bool = Field(default=False, description="JSON log format")
    levels: dict[str, str] = Field(
        default_factory=dict,
        description="Per-logger level overrides",
    )
    sampling: SamplingConfig = Field(
        default_factory=SamplingConfig,
        description="Log sampling configuration",
    )
    redaction: RedactionConfig = Field(
        default_factory=RedactionConfig,
        description="Log event field redaction configuration",
    )

    @model_validator(mode="after")
    def validate_level(self) -> LoggingConfig:
        """Validate and normalize the global log level."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if self.level.upper() not in valid_levels:
            self.level = "INFO"
        return self

    @model_validator(mode="after")
    def validate_levels(self) -> LoggingConfig:
        """Validate/normalize per-logger level overrides.

        Any entry with an invalid level name is replaced with ``"INFO"``.
        Levels are upper-cased for consistency.
        """
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        cleaned: dict[str, str] = {}
        for logger_name, lvl in self.levels.items():
            lvl_up = lvl.upper()
            if lvl_up not in valid_levels:
                lvl_up = "INFO"
            cleaned[logger_name] = lvl_up
        self.levels = cleaned
        return self


__all__ = ["LoggingConfig"]
