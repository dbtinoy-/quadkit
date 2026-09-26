"""OTel, Prometheus, and SLO exporter configuration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from quadkit.config import BaseConfig
from quadkit.monitor import constants as monitor_const
from quadkit.validation import ConfigDict, Field, field_validator


@dataclass(init=False)
class OTelExporterConfig(BaseConfig):
    """Configuration for OTel exporters."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    type: str = Field("console", description="Exporter type (console, jaeger, otlp)")
    endpoint: str | None = Field(None, description="Collector endpoint URL")
    headers: dict[str, str] = Field(
        default_factory=dict,
        description="Custom headers for OTLP",
    )


@dataclass(init=False)
class OpenTelemetryConfig(BaseConfig):
    """Configuration for OpenTelemetry backend.

    Attributes:
        endpoint: OTLP endpoint URL.
        headers: Headers to send with OTLP requests.
        insecure: Use insecure connection (no TLS).
        timeout: Export timeout in seconds.
        compression: Compression type (none, gzip).
        batch_size: Batch size for exports.
        export_interval: Export interval in seconds.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    endpoint: str | None = Field(None, description="OTLP endpoint URL")
    headers: dict[str, str] = Field(
        default_factory=dict,
        description="OTLP request headers",
    )
    insecure: bool = Field(False, description="Use insecure connection")
    timeout: float = Field(30.0, ge=1.0, description="Export timeout seconds")
    compression: str = Field("none", description="Compression type (none, gzip)")
    batch_size: int = Field(512, ge=1, description="Export batch size")
    export_interval: float = Field(5.0, ge=0.1, description="Export interval seconds")
    tracing_exporters: list[OTelExporterConfig] = Field(
        default_factory=lambda: [OTelExporterConfig()],
        description="List of tracing exporters to build.",
    )
    metrics_exporters: list[OTelExporterConfig] = Field(
        default_factory=lambda: [OTelExporterConfig()],
        description="List of metrics exporters to build.",
    )

    @field_validator("compression")
    @classmethod
    def validate_compression(cls, v: str) -> str:
        """Validate compression type."""
        valid = {"none", "gzip"}
        if v.lower() not in valid:
            raise ValueError(f"compression must be one of {valid}")
        return v.lower()


@dataclass(init=False)
class PrometheusConfig(BaseConfig):
    """Configuration for Prometheus backend.

    Attributes:
        port: Port for metrics HTTP server.
        path: Path for metrics endpoint.
        enable_default_metrics: Enable default process metrics.
        pushgateway_url: Optional Pushgateway URL for push-based metrics.
        push_interval: Interval for pushing metrics to Pushgateway (seconds).
        store_in_db: Whether to persist metric observations to the database.
        metrics_table: Name of the metrics table to write samples to.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    port: int = Field(
        monitor_const.DEFAULT_PROMETHEUS_PORT,
        ge=1,
        le=65535,
        description="Metrics server port",
    )
    path: str = Field("/metrics", description="Metrics endpoint path")
    enable_default_metrics: bool = Field(
        True,
        description="Enable default process metrics",
    )
    pushgateway_url: str | None = Field(
        None,
        description="Pushgateway URL for push-based metrics",
    )
    push_interval: float = Field(
        10.0,
        ge=1.0,
        description="Push interval for Pushgateway",
    )
    # DB storage options
    store_in_db: bool = Field(False, description="Persist metrics observations to DB")
    metrics_table: str = Field(
        "metrics_samples",
        description="Table name for metrics samples",
    )


@dataclass(init=False)
class SLOConfig(BaseConfig):
    """Configuration for SLO evaluation and alerting.

    Attributes:
        enabled: Whether the SLO evaluation worker runs.
        evaluation_interval: Seconds between SLO evaluation cycles (default 60).
        suppression_window_seconds: Min seconds between duplicate alerts (default 300).
        alert_channels: List of alert channel names to dispatch SLO violations to.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    enabled: bool = Field(True, description="Enable periodic SLO evaluation worker")
    evaluation_interval: float = Field(
        60.0, ge=1.0, description="SLO evaluation interval in seconds"
    )
    suppression_window_seconds: int = Field(
        300, ge=0, description="Alert suppression window in seconds"
    )
    alert_channels: list[str] = Field(
        default_factory=list,
        description="Alert channel names for SLO violation dispatch",
    )


__all__ = [
    "OTelExporterConfig",
    "OpenTelemetryConfig",
    "PrometheusConfig",
    "SLOConfig",
]
