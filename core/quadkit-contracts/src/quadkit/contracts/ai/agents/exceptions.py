"""Agent exception definitions."""

from __future__ import annotations

from typing import Any

from quadkit.contracts.exceptions.base import QuadkitError


class AgentError(QuadkitError):
    """Base exception for all agent errors."""

    _code = "QK_ERR_AGT_001"

    def __init__(self, message: str = "Agent error", **kwargs: Any) -> None:
        super().__init__(
            message=message,
            **kwargs,
        )


class ToolError(AgentError):
    """Base exception for tool errors."""

    _code = "QK_ERR_AGT_002"

    def __init__(self, message: str = "Tool error", **kwargs: Any) -> None:
        super().__init__(
            message=message,
            **kwargs,
        )


class StrategyError(AgentError):
    """Reasoning strategy failed.

    Raised when the agent's strategy encounters an error
    during reasoning (LLM failure, invalid response, etc.).
    """

    _code = "QK_ERR_AGT_003"

    def __init__(
        self,
        message: str = "Strategy execution failed",
        *,
        strategy_name: str | None = None,
        **kwargs: Any,
    ) -> None:
        details = kwargs.pop("details", {})
        if strategy_name:
            details["strategy"] = strategy_name
        super().__init__(
            message=message,
            details=details,
            **kwargs,
        )
