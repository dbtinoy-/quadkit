"""Agent constants — error codes, metric names, and span names.

Centralised string constants used across the agents package to prevent
magic-string drift between modules.
"""

from __future__ import annotations

import importlib.metadata

try:
    __version__: str = importlib.metadata.version("quadkit-ai-agents")
except ImportError:
    __version__ = "0.0.0"

# ---------------------------------------------------------------------------
# Environment configuration
# ---------------------------------------------------------------------------

ENV_PREFIX: str = "QK_AI_AGENTS__"
ENV_NESTED_DELIMITER: str = "__"

# ---------------------------------------------------------------------------
# Error codes
# ---------------------------------------------------------------------------

ERROR_AGENT_CONFIG: str = "AGENT_CONFIG_ERROR"
ERROR_AGENT_EXECUTION: str = "AGENT_EXECUTION_ERROR"
ERROR_TOOL_NOT_FOUND: str = "TOOL_NOT_FOUND"
ERROR_TOOL_EXECUTION: str = "TOOL_EXECUTION_ERROR"
ERROR_TOOL_ACCESS_DENIED: str = "TOOL_ACCESS_DENIED"
ERROR_MAX_ITERATIONS_EXCEEDED: str = "MAX_ITERATIONS_EXCEEDED"
ERROR_BUDGET_EXCEEDED: str = "BUDGET_EXCEEDED"

# ---------------------------------------------------------------------------
# MetricProtocol names
# ---------------------------------------------------------------------------

METRIC_AGENT_EXECUTIONS_TOTAL: str = "agent.executions.total"
METRIC_AGENT_EXECUTION_DURATION_MS: str = "agent.execution.duration_ms"
METRIC_AGENT_EXECUTION_TOKENS: str = "agent.execution.tokens"
METRIC_AGENT_EXECUTION_STEPS: str = "agent.execution.steps"
METRIC_AGENT_EXECUTION_TOOL_CALLS: str = "agent.execution.tool_calls"
METRIC_AGENT_EXECUTIONS_ERRORS: str = "agent.executions.errors"
METRIC_AGENT_TOOL_CALLS_TOTAL: str = "agent.tool_calls.total"
METRIC_AGENT_TOOL_CALL_DURATION_MS: str = "agent.tool_call.duration_ms"
METRIC_AGENT_TOOL_CALLS_SUCCESS: str = "agent.tool_calls.success"
METRIC_AGENT_TOOL_CALLS_FAILURE: str = "agent.tool_calls.failure"
METRIC_AGENT_TOOL_CALLS_FAILED: str = "agent.tool_calls.failed"
METRIC_AGENT_GOVERNANCE_DENIED: str = "agent.governance.denied"

# ---------------------------------------------------------------------------
# Span names
# ---------------------------------------------------------------------------

SPAN_AGENT_EXECUTE: str = "agent.execute"
SPAN_AGENT_TOOL: str = "agent.tool"
SPAN_AGENT_LLM: str = "agent.llm"

__all__ = [
    "ENV_NESTED_DELIMITER",
    "ENV_PREFIX",
    "ERROR_AGENT_CONFIG",
    "ERROR_AGENT_EXECUTION",
    "ERROR_BUDGET_EXCEEDED",
    "ERROR_MAX_ITERATIONS_EXCEEDED",
    "ERROR_TOOL_ACCESS_DENIED",
    "ERROR_TOOL_EXECUTION",
    "ERROR_TOOL_NOT_FOUND",
    "METRIC_AGENT_EXECUTIONS_ERRORS",
    "METRIC_AGENT_EXECUTIONS_TOTAL",
    "METRIC_AGENT_EXECUTION_DURATION_MS",
    "METRIC_AGENT_EXECUTION_STEPS",
    "METRIC_AGENT_EXECUTION_TOKENS",
    "METRIC_AGENT_EXECUTION_TOOL_CALLS",
    "METRIC_AGENT_GOVERNANCE_DENIED",
    "METRIC_AGENT_TOOL_CALLS_FAILED",
    "METRIC_AGENT_TOOL_CALLS_FAILURE",
    "METRIC_AGENT_TOOL_CALLS_SUCCESS",
    "METRIC_AGENT_TOOL_CALLS_TOTAL",
    "METRIC_AGENT_TOOL_CALL_DURATION_MS",
    "SPAN_AGENT_EXECUTE",
    "SPAN_AGENT_LLM",
    "SPAN_AGENT_TOOL",
    "__version__",
]
