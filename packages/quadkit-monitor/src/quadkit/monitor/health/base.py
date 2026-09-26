from __future__ import annotations

from abc import ABC, abstractmethod

from quadkit.contracts.core import HealthCheckResult


class HealthCheck(ABC):
    """Base class for health checks."""

    def __init__(self, name: str, critical: bool = True):
        self.name = name
        self.critical = critical

    @abstractmethod
    async def check(self) -> HealthCheckResult:
        pass
