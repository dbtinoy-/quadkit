"""Metrics collection and reporting for LLM providers.

Provides comprehensive metrics tracking including latency, error rates,
token usage, costs, and cache performance across all providers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from quadkit.logging import (
    get_logger,
)

logger = get_logger(__name__)


class MetricType(StrEnum):
    """Types of metrics that can be collected."""

    LATENCY = "latency"
    ERROR = "error"
    TOKEN_USAGE = "token_usage"  # noqa: S105  # metric type name, not a credential
    COST = "cost"
    CACHE = "cache"
    RATE_LIMIT = "rate_limit"
    HEALTH = "health"


@dataclass
class TimingMetrics:
    """Latency and timing metrics for a provider.

    Attributes:
        provider: Provider name
        model_id: Model identifier
        request_count: Total number of requests
        total_requests: Total number of requests (alias for request_count)
        error_count: Total number of errors
        min_latency_ms: Minimum request latency in milliseconds
        max_latency_ms: Maximum request latency in milliseconds
        avg_latency_ms: Average request latency in milliseconds
        p95_latency_ms: 95th percentile latency
        p99_latency_ms: 99th percentile latency
    """

    provider: str
    model_id: str
    request_count: int = 0
    error_count: int = 0
    min_latency_ms: float = 0.0
    max_latency_ms: float = 0.0
    avg_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    _latencies: list[float] = field(default_factory=list, repr=False)

    @property
    def total_requests(self) -> int:
        """Total number of requests (live alias for :attr:`request_count`)."""
        return self.request_count

    def record_latency(self, latency_ms: float) -> None:
        """Record a request latency.

        Args:
            latency_ms: Latency in milliseconds
        """
        self._latencies.append(latency_ms)
        self.request_count += 1

        if self.request_count == 1 or latency_ms < self.min_latency_ms:
            self.min_latency_ms = latency_ms

        self.max_latency_ms = max(self.max_latency_ms, latency_ms)

        # Recalculate averages
        self._recalculate_percentiles()

    def _recalculate_percentiles(self) -> None:
        """Recalculate average and percentile metrics."""
        if not self._latencies:
            return

        sorted_latencies = sorted(self._latencies)
        self.avg_latency_ms = sum(sorted_latencies) / len(sorted_latencies)

        # Calculate percentiles
        if len(sorted_latencies) >= 20:
            idx_95 = int(len(sorted_latencies) * 0.95)
            self.p95_latency_ms = sorted_latencies[idx_95]
            idx_99 = int(len(sorted_latencies) * 0.99)
            self.p99_latency_ms = sorted_latencies[idx_99]


@dataclass
class ErrorMetrics:
    """Error tracking and rates for a provider.

    Attributes:
        provider: Provider name
        model_id: Model identifier
        total_requests: Total number of requests attempted
        error_count: Total number of errors
        rate_limit_errors: Number of rate limit errors
        timeout_errors: Number of timeout errors
        auth_errors: Number of authentication errors
        other_errors: Number of other errors
    """

    provider: str
    model_id: str
    total_requests: int = 0
    error_count: int = 0
    rate_limit_errors: int = 0
    timeout_errors: int = 0
    auth_errors: int = 0
    other_errors: int = 0

    @property
    def error_rate(self) -> float:
        """Calculate current error rate as percentage (0-100)."""
        if self.total_requests == 0:
            return 0.0
        return (self.error_count / self.total_requests) * 100

    def record_error(self, error_type: str) -> None:
        """Record an error occurrence.

        Args:
            error_type: One of 'rate_limit', 'timeout', 'auth', 'other'
        """
        self.error_count += 1

        if error_type == "rate_limit":
            self.rate_limit_errors += 1
        elif error_type == "timeout":
            self.timeout_errors += 1
        elif error_type == "auth":
            self.auth_errors += 1
        else:
            self.other_errors += 1

    def record_request(self) -> None:
        """Record a request attempt."""
        self.total_requests += 1


@dataclass
class CacheMetrics:
    """Cache performance metrics.

    Attributes:
        cache_hits: Number of cache hits
        cache_misses: Number of cache misses
        tokens_saved: Total tokens saved by caching
        bytes_saved: Total bytes saved by caching
    """

    cache_hits: int = 0
    cache_misses: int = 0
    tokens_saved: int = 0
    bytes_saved: int = 0

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate as percentage (0-100)."""
        total = self.cache_hits + self.cache_misses
        if total == 0:
            return 0.0
        return (self.cache_hits / total) * 100


@dataclass
class UsageMetrics:
    """Token usage and cost tracking for a provider/model pair.

    Attributes:
        provider: Provider name
        model_id: Model identifier
        prompt_tokens: Total prompt tokens
        completion_tokens: Total completion tokens
        cost_usd: Total estimated cost in US dollars
    """

    provider: str
    model_id: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0

    @property
    def total_tokens(self) -> int:
        """Total tokens (prompt + completion)."""
        return self.prompt_tokens + self.completion_tokens


@dataclass
class MetricsSnapshot:
    """Snapshot of all collected metrics at a point in time.

    Attributes:
        timestamp: When the snapshot was taken
        metric_type: Type of metric
        provider: Provider name
        data: The actual metric data
    """

    timestamp: datetime
    metric_type: MetricType
    provider: str
    data: dict[str, Any]


class MetricsCollector:
    """Central metrics collection and aggregation.

    Collects metrics from all providers and models, provides query
    interfaces, and exports data for monitoring and billing.
    """

    def __init__(self) -> None:
        """Initialize metrics collector."""
        self._timing_metrics: dict[tuple[str, str], TimingMetrics] = {}
        self._error_metrics: dict[tuple[str, str], ErrorMetrics] = {}
        self._cache_metrics: dict[str, CacheMetrics] = {}
        self._usage_metrics: dict[tuple[str, str], UsageMetrics] = {}
        self._snapshots: list[MetricsSnapshot] = []
        self._start_time = datetime.now(UTC)

    def get_timing_metrics(self, provider: str, model_id: str) -> TimingMetrics | None:
        """Get timing metrics for a provider/model.

        Args:
            provider: Provider name
            model_id: Model identifier

        Returns:
            TimingMetrics if available, None otherwise
        """
        return self._timing_metrics.get((provider, model_id))

    def get_error_metrics(self, provider: str, model_id: str) -> ErrorMetrics | None:
        """Get error metrics for a provider/model.

        Args:
            provider: Provider name
            model_id: Model identifier

        Returns:
            ErrorMetrics if available, None otherwise
        """
        return self._error_metrics.get((provider, model_id))

    def get_cache_metrics(self) -> dict[str, CacheMetrics]:
        """Get all cache metrics.

        Returns:
            Dictionary of provider name to CacheMetrics
        """
        return self._cache_metrics.copy()

    def get_usage_metrics(self, provider: str, model_id: str) -> UsageMetrics | None:
        """Get token usage and cost metrics for a provider/model.

        Args:
            provider: Provider name
            model_id: Model identifier

        Returns:
            UsageMetrics if available, None otherwise
        """
        return self._usage_metrics.get((provider, model_id))

    def record_request(
        self,
        provider: str,
        model_id: str,
        latency_ms: float,
        error: bool = False,
        error_type: str | None = None,
        *,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        cost_usd: float = 0.0,
    ) -> None:
        """Record a request and its metrics.

        Args:
            provider: Provider name
            model_id: Model identifier
            latency_ms: Request latency in milliseconds
            error: Whether the request resulted in an error
            error_type: Type of error (only if error=True)
            prompt_tokens: Prompt tokens consumed by the request
            completion_tokens: Completion tokens produced by the request
            cost_usd: Estimated cost of the request in US dollars
        """
        key = (provider, model_id)

        # Record timing
        timing = self._timing_metrics.setdefault(
            key,
            TimingMetrics(provider=provider, model_id=model_id),
        )
        timing.record_latency(latency_ms)

        # Record errors
        errors = self._error_metrics.setdefault(
            key,
            ErrorMetrics(provider=provider, model_id=model_id),
        )
        errors.record_request()

        if error:
            errors.record_error(error_type or "other")

        # Record token usage and cost
        usage = self._usage_metrics.setdefault(
            key,
            UsageMetrics(provider=provider, model_id=model_id),
        )
        usage.prompt_tokens += prompt_tokens
        usage.completion_tokens += completion_tokens
        usage.cost_usd += cost_usd

        logger.debug(
            "metrics_recorded",
            latency_ms=latency_ms,
            error=error,
        )

    def record_cache_hit(self, provider: str, tokens_saved: int = 0) -> None:
        """Record a cache hit.

        Args:
            provider: Provider name
            tokens_saved: Number of tokens saved by the cache hit
        """
        cache = self._cache_metrics.setdefault(provider, CacheMetrics())
        cache.cache_hits += 1
        cache.tokens_saved += tokens_saved

    def record_cache_miss(self, provider: str) -> None:
        """Record a cache miss.

        Args:
            provider: Provider name
        """
        cache = self._cache_metrics.setdefault(provider, CacheMetrics())
        cache.cache_misses += 1

    def take_snapshot(self, provider: str, metric_type: MetricType) -> None:
        """Take a snapshot of current metrics.

        Args:
            provider: Provider name
            metric_type: Type of metrics to snapshot
        """
        data: dict[str, Any] = {}

        if metric_type == MetricType.LATENCY:
            # Aggregate timing metrics across all models for this provider
            metrics_for_provider = [
                m for (p, m_id), m in self._timing_metrics.items() if p == provider
            ]
            if metrics_for_provider:
                total_requests = sum(m.request_count for m in metrics_for_provider)
                # Weight per-model averages by request count — a simple mean
                # of per-model means would let a 1-request model distort the
                # provider average as much as a 100k-request one.
                avg_latency = (
                    sum(
                        m.avg_latency_ms * m.request_count for m in metrics_for_provider
                    )
                    / total_requests
                    if total_requests > 0
                    else 0.0
                )
                data = {
                    "request_count": total_requests,
                    "avg_latency_ms": round(avg_latency, 2),
                }
        elif metric_type == MetricType.ERROR:
            # Aggregate error metrics across all models for this provider
            error_entries = [
                m for (p, m_id), m in self._error_metrics.items() if p == provider
            ]
            if error_entries:
                total_requests = sum(e.total_requests for e in error_entries)
                error_count = sum(e.error_count for e in error_entries)
                error_rate = (
                    (error_count / total_requests * 100) if total_requests > 0 else 0.0
                )
                data = {
                    "total_requests": total_requests,
                    "error_count": error_count,
                    "error_rate": round(error_rate, 2),
                }
        elif metric_type == MetricType.TOKEN_USAGE:
            # Aggregate token usage across all models for this provider
            usage_for_provider = [
                m for (p, m_id), m in self._usage_metrics.items() if p == provider
            ]
            if usage_for_provider:
                prompt_tokens = sum(m.prompt_tokens for m in usage_for_provider)
                completion_tokens = sum(m.completion_tokens for m in usage_for_provider)
                data = {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": prompt_tokens + completion_tokens,
                }
        elif metric_type == MetricType.COST:
            # Aggregate cost across all models for this provider
            usage_for_provider = [
                m for (p, m_id), m in self._usage_metrics.items() if p == provider
            ]
            if usage_for_provider:
                cost_usd = sum(m.cost_usd for m in usage_for_provider)
                data = {"cost_usd": round(cost_usd, 6)}
        elif metric_type == MetricType.CACHE:
            cache = self._cache_metrics.get(provider)
            if cache:
                data = {
                    "hits": cache.cache_hits,
                    "misses": cache.cache_misses,
                    "hit_rate": round(cache.hit_rate, 2),
                    "tokens_saved": cache.tokens_saved,
                }

        if data:
            snapshot = MetricsSnapshot(
                timestamp=datetime.now(UTC),
                metric_type=metric_type,
                provider=provider,
                data=data,
            )
            self._snapshots.append(snapshot)

    def get_snapshots(
        self,
        provider: str | None = None,
        metric_type: MetricType | None = None,
    ) -> list[MetricsSnapshot]:
        """Get recorded snapshots, optionally filtered.

        Args:
            provider: Only snapshots for this provider (None = all).
            metric_type: Only snapshots of this type (None = all).

        Returns:
            Copy of the matching snapshot list, oldest first.
        """
        return [
            s
            for s in self._snapshots
            if (provider is None or s.provider == provider)
            and (metric_type is None or s.metric_type == metric_type)
        ]

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of all collected metrics.

        Returns:
            Dictionary with timing, error, and cache summaries
        """
        return {
            "uptime_seconds": (datetime.now(UTC) - self._start_time).total_seconds(),
            "timing_metrics": {
                f"{p}:{m}": {
                    "requests": t.request_count,
                    "avg_latency_ms": round(t.avg_latency_ms, 2),
                }
                for (p, m), t in self._timing_metrics.items()
            },
            "error_metrics": {
                f"{p}:{m}": {
                    "total_requests": e.total_requests,
                    "error_rate": round(e.error_rate, 2),
                }
                for (p, m), e in self._error_metrics.items()
            },
            "cache_metrics": {
                p: {
                    "hit_rate": round(c.hit_rate, 2),
                    "tokens_saved": c.tokens_saved,
                }
                for p, c in self._cache_metrics.items()
            },
        }
