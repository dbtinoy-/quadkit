"""Agent configuration for the Quadkit framework."""

from __future__ import annotations

from typing import ClassVar, cast

from quadkit.ai.agents import constants as const
from quadkit.config.base import BaseConfig
from quadkit.contracts.core.config import Environment
from quadkit.validation import ConfigDict, Field

ENV_PREFIX: str = const.ENV_PREFIX
ENV_NESTED_DELIMITER: str = const.ENV_NESTED_DELIMITER


class AgentConfig(BaseConfig):
    """Configuration for the agent system.

    Attributes:
        max_iterations: Maximum reasoning iterations per execution.
        default_temperature: Default temperature for LLM calls.
        default_max_tokens: Default max tokens for LLM responses.
        tool_max_retries: Maximum retry attempts for transient tool errors.
        enable_tracing: Enable OpenTelemetry tracing.
        enable_metrics: Enable Prometheus metrics.

    Example:
        >>> config = AgentConfig(
        ...     max_iterations=10,
        ...     default_temperature=0.7
        ... )
    """

    config_section: ClassVar[str] = "ai_agents"

    model_config: ClassVar[ConfigDict] = cast(
        "ConfigDict",
        {
            "env_prefix": ENV_PREFIX,
            "env_nested_delimiter": ENV_NESTED_DELIMITER,
            "extra": "ignore",
        },
    )

    enabled: bool = Field(default=True, description="Enable the AI agents subsystem")
    name: str = "ai_agents"
    env: Environment | None = Field(None, description="Deployment environment")

    max_iterations: int = Field(
        default=10,
        ge=1,
        description="Maximum reasoning iterations per execution",
    )

    default_temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="Default temperature for LLM calls",
    )

    default_max_tokens: int = Field(
        default=2048,
        ge=1,
        description="Default max tokens for LLM responses",
    )

    tool_max_retries: int = Field(
        default=3,
        ge=1,
        description=(
            "Number of retries for transient tool execution errors "
            "(ConnectionError, TimeoutError, OSError)"
        ),
    )

    enable_tracing: bool = Field(
        default=True,
        description="Enable OpenTelemetry tracing",
    )

    enable_metrics: bool = Field(
        default=True,
        description="Enable Prometheus metrics",
    )


__all__ = ["ENV_PREFIX", "AgentConfig"]
