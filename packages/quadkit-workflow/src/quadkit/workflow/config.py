"""Bulk operation configuration and graph engine configuration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

from quadkit.config.base import BaseConfig
from quadkit.validation import ConfigDict, Field
from quadkit.workflow.constants import DEFAULT_PIPELINE_TIMEOUT

if TYPE_CHECKING:
    from quadkit.contracts.core.config import ConfigIssue, Environment
    from quadkit.contracts.infra.resilience.models import CircuitBreakerConfig

ENV_PREFIX: str = "QK_WORKFLOW__"
ENV_NESTED_DELIMITER: str = "__"
GRAPH_ENV_PREFIX: str = "QK_WORKFLOW__GRAPH__"


@dataclass(init=False)
class BulkOperationConfig(BaseConfig):
    """Configuration for bulk operations and pipeline execution.

    Attributes:
        batch_size: Number of items per batch.
        max_concurrency: Maximum number of concurrent operations.
        timeout: Operation timeout in seconds.
        retry_attempts: Number of retry attempts.
        retry_delay: Delay between retries in seconds.
        enable_progress_tracking: Whether to track progress.
        circuit_breaker_config: Optional circuit breaker configuration.
        pipeline_timeout: Default pipeline execution timeout in seconds.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    batch_size: int = Field(default=10, gt=0, description="Number of items per batch.")
    max_concurrency: int = Field(
        default=5, gt=0, description="Maximum concurrent operations."
    )
    timeout: float = Field(
        default=300.0, gt=0, description="Operation timeout in seconds."
    )
    retry_attempts: int = Field(
        default=3, ge=0, description="Number of retry attempts on failure."
    )
    retry_delay: float = Field(
        default=1.0, ge=0, description="Delay in seconds between retries."
    )
    enable_progress_tracking: bool = Field(
        default=True, description="Track operation progress."
    )
    circuit_breaker_config: CircuitBreakerConfig | None = Field(
        default=None,
        description="Optional circuit breaker configuration for bulk operations.",
    )
    pipeline_timeout: float = Field(
        default=DEFAULT_PIPELINE_TIMEOUT,
        gt=0,
        description="Default pipeline execution timeout in seconds.",
    )


@dataclass(init=False)
class GraphConfig(BaseConfig):
    """Configuration for the workflow graph engine.

    Attributes:
        enabled: Enable the graph workflow subsystem.
        max_iterations: Maximum graph traversal steps (anti-infinite-loop guard).
        node_timeout: Per-node execution timeout in seconds. 0 = no limit.
        total_timeout: Total workflow timeout in seconds. 0 = no limit.
        checkpoint_enabled: Persist state checkpoints for resumption after failures.
        parallel_branches: Execute independent parallel branches via asyncio.gather.
        max_parallel_branches: Max parallel branches at once. 0 = unlimited.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    config_section: ClassVar[str] = "workflow"
    name: str = "workflow"
    enabled: bool = Field(
        default=True, description="Enable the graph workflow subsystem"
    )

    max_iterations: int = Field(
        default=25,
        ge=1,
        description="Maximum graph traversal steps (anti-infinite-loop guard)",
    )
    node_timeout: float = Field(
        default=120.0,
        ge=0.0,
        description="Per-node execution timeout in seconds. 0 = no limit",
    )
    total_timeout: float = Field(
        default=0.0,
        ge=0.0,
        description="Total workflow timeout in seconds. 0 = no limit",
    )
    checkpoint_enabled: bool = Field(
        default=False,
        description="Persist state checkpoints for resumption after failures",
    )
    parallel_branches: bool = Field(
        default=True,
        description="Execute independent parallel branches via asyncio.gather",
    )
    max_parallel_branches: int = Field(
        default=0, ge=0, description="Max parallel branches at once. 0 = unlimited"
    )

    def validate_for_environment(
        self, env: Environment | None = None
    ) -> list[ConfigIssue]:
        """Check config is safe for the target environment.

        Args:
            env: Target deployment environment.

        Returns:
            List of configuration issues (empty if all OK).
        """
        issues: list[ConfigIssue] = []
        return issues


@dataclass(init=False)
class ContentCheckpointConfig(BaseConfig):
    """Configuration for content-addressed checkpointing.

    Attributes:
        enabled: Enable content-addressed checkpointing.
        inline_threshold_bytes: Max bytes to store inline; beyond this
            threshold outputs are offloaded to blob store.
        default_ttl_seconds: Default TTL for cache-backed stores.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    enabled: bool = Field(
        default=True, description="Enable content-addressed checkpointing."
    )
    inline_threshold_bytes: int = Field(
        default=1_048_576,
        gt=0,
        description="Max inline bytes before blob offload.",
    )
    default_ttl_seconds: int = Field(
        default=86400,
        gt=0,
        description="Default TTL for cache-backed checkpoint stores.",
    )


__all__ = ["BulkOperationConfig", "ContentCheckpointConfig", "GraphConfig"]
