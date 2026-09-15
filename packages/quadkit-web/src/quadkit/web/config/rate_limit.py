"""Rate limiting and role guard configuration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from quadkit.config import BaseConfig
from quadkit.validation import ConfigDict, Field, model_validator
from quadkit.web import constants as const


@dataclass(init=False)
class RateLimitRuleConfig(BaseConfig):
    """Rate limit rule for a specific path pattern."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    requests: int = Field(default=100, ge=1, description="Max requests per window")
    window: int = Field(default=60, ge=1, description="Window size in seconds")
    burst: int | None = Field(
        default=None,
        description="Burst capacity (defaults to requests)",
    )

    @property
    def effective_burst(self) -> int:
        """Get burst capacity, defaulting to requests if not set."""
        return self.burst if self.burst is not None else self.requests


@dataclass(init=False)
class RateLimitConfig(BaseConfig):
    """Rate limiting configuration with per-path rules."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    enabled: bool = Field(
        default=False,
        description=(
            "Enable rate limiting. When true, RateLimitMiddleware enforces "
            "the matched per-path rule or the default_limit/default_window "
            "on every HTTP request."
        ),
    )
    default_limit: int = Field(
        default=const.DEFAULT_RATE_LIMIT_REQUESTS, description="Max requests per window"
    )
    default_window: int = Field(
        default=const.DEFAULT_RATE_LIMIT_WINDOW, description="Window size in seconds"
    )
    whitelist_ips: list[str] = Field(
        default_factory=list,
        description="Exempt IP addresses",
    )
    storage_backend: str = Field(
        default="memory",
        description="Storage backend (memory/redis)",
    )

    # Per-path rules — enforced by RateLimitMiddleware via get_rule()
    rules: dict[str, RateLimitRuleConfig] = Field(
        default_factory=dict,
        description="Per-path rate limit rules; longest-prefix match wins",
    )

    @model_validator(mode="after")
    def validate_rate_limit(self) -> RateLimitConfig:
        """Validate rate limit settings."""
        if self.enabled:
            if self.default_limit <= 0:
                raise ValueError("Rate limit 'default_limit' must be greater than 0.")
            if self.default_window <= 0:
                raise ValueError("Rate limit 'default_window' must be greater than 0.")
        return self

    def get_rule(self, path: str) -> RateLimitRuleConfig | None:
        """Get rate limit rule for a path (longest prefix match).

        Prefix matching honours path-segment boundaries: a rule for
        ``/api`` matches ``/api`` and ``/api/users`` but **not**
        ``/apifoo``.
        """
        # Exact match first
        if path in self.rules:
            return self.rules[path]

        # Longest prefix match
        best_match = None
        best_length = 0
        for pattern, rule in self.rules.items():
            if not path.startswith(pattern) or len(pattern) <= best_length:
                continue
            # Enforce a "/" boundary at the end of the matched prefix so
            # "/api" does not match "/apifoo" (patterns ending in "/"
            # already carry their own boundary).
            if (
                len(path) > len(pattern)
                and not pattern.endswith("/")
                and path[len(pattern)] != "/"
            ):
                continue
            best_match = rule
            best_length = len(pattern)

        return best_match


@dataclass(init=False)
class RoleGuardRuleConfig(BaseConfig):
    """One role guard rule entry from ``web.role_guard.rules``.

    Attributes:
        path: Exact path to guard. A trailing ``/**`` matches every path
            under that prefix.
        roles: Role identifiers allowed to pass.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    path: str = Field(
        default="", description="Path to guard ('/**' suffix matches the prefix)"
    )
    roles: list[str] = Field(
        default_factory=list,
        description="Role identifiers allowed to pass",
    )


@dataclass(init=False)
class RoleGuardConfig(BaseConfig):
    """Role guard settings from ``web.role_guard``.

    Absent by default; a single gating rule is enough for most applications
    (e.g. ``web.role_guard.rules: [{path: /api/users, roles: [admin]}]``).

    Attributes:
        rules: Rules applied in declaration order; first match wins.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    rules: list[RoleGuardRuleConfig] = Field(
        default_factory=list,
        description="Role guard rules in declaration order",
    )

    @property
    def enabled(self) -> bool:
        """Return True when at least one rule is declared."""
        return bool(self.rules)


__all__ = [
    "RateLimitConfig",
    "RateLimitRuleConfig",
    "RoleGuardConfig",
    "RoleGuardRuleConfig",
]
