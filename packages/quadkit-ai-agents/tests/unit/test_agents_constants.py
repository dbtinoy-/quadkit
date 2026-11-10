"""Tests for AI agents constants."""

import pytest

from quadkit.ai.agents import constants


class TestVersion:
    """Tests for package version."""

    def test_version_is_string(self) -> None:
        """Test __version__ is a string."""
        assert isinstance(constants.__version__, str)

    def test_version_format(self) -> None:
        """Test version follows semver-like format."""
        version = constants.__version__
        assert version.count(".") >= 2


class TestEnvironmentConstants:
    """Tests for environment configuration constants."""

    def test_env_prefix(self) -> None:
        """Test ENV_PREFIX value."""
        assert constants.ENV_PREFIX == "QK_AI_AGENTS__"

    def test_env_nested_delimiter(self) -> None:
        """Test ENV_NESTED_DELIMITER value."""
        assert constants.ENV_NESTED_DELIMITER == "__"


class TestErrorCodes:
    """Tests for error code constants."""

    def test_error_agent_config(self) -> None:
        assert constants.ERROR_AGENT_CONFIG == "AGENT_CONFIG_ERROR"

    def test_error_agent_execution(self) -> None:
        assert constants.ERROR_AGENT_EXECUTION == "AGENT_EXECUTION_ERROR"

    def test_error_tool_not_found(self) -> None:
        assert constants.ERROR_TOOL_NOT_FOUND == "TOOL_NOT_FOUND"

    def test_error_tool_execution(self) -> None:
        assert constants.ERROR_TOOL_EXECUTION == "TOOL_EXECUTION_ERROR"

    def test_error_tool_access_denied(self) -> None:
        assert constants.ERROR_TOOL_ACCESS_DENIED == "TOOL_ACCESS_DENIED"

    def test_error_max_iterations_exceeded(self) -> None:
        assert constants.ERROR_MAX_ITERATIONS_EXCEEDED == "MAX_ITERATIONS_EXCEEDED"

    def test_error_budget_exceeded(self) -> None:
        assert constants.ERROR_BUDGET_EXCEEDED == "BUDGET_EXCEEDED"


class TestMetricNames:
    """Tests for metric name constants."""

    def test_metric_agent_executions_total(self) -> None:
        assert constants.METRIC_AGENT_EXECUTIONS_TOTAL == "agent.executions.total"

    def test_metric_agent_execution_duration_ms(self) -> None:
        assert constants.METRIC_AGENT_EXECUTION_DURATION_MS == "agent.execution.duration_ms"

    def test_metric_agent_execution_tokens(self) -> None:
        assert constants.METRIC_AGENT_EXECUTION_TOKENS == "agent.execution.tokens"

    def test_metric_agent_execution_steps(self) -> None:
        assert constants.METRIC_AGENT_EXECUTION_STEPS == "agent.execution.steps"

    def test_metric_agent_execution_tool_calls(self) -> None:
        assert constants.METRIC_AGENT_EXECUTION_TOOL_CALLS == "agent.execution.tool_calls"

    def test_metric_agent_executions_errors(self) -> None:
        assert constants.METRIC_AGENT_EXECUTIONS_ERRORS == "agent.executions.errors"

    def test_metric_agent_tool_calls_total(self) -> None:
        assert constants.METRIC_AGENT_TOOL_CALLS_TOTAL == "agent.tool_calls.total"

    def test_metric_agent_tool_call_duration_ms(self) -> None:
        assert constants.METRIC_AGENT_TOOL_CALL_DURATION_MS == "agent.tool_call.duration_ms"

    def test_metric_agent_tool_calls_success(self) -> None:
        assert constants.METRIC_AGENT_TOOL_CALLS_SUCCESS == "agent.tool_calls.success"

    def test_metric_agent_tool_calls_failure(self) -> None:
        assert constants.METRIC_AGENT_TOOL_CALLS_FAILURE == "agent.tool_calls.failure"

    def test_metric_agent_tool_calls_failed(self) -> None:
        assert constants.METRIC_AGENT_TOOL_CALLS_FAILED == "agent.tool_calls.failed"

    def test_metric_agent_governance_denied(self) -> None:
        assert constants.METRIC_AGENT_GOVERNANCE_DENIED == "agent.governance.denied"


class TestSpanNames:
    """Tests for span name constants."""

    def test_span_agent_execute(self) -> None:
        assert constants.SPAN_AGENT_EXECUTE == "agent.execute"

    def test_span_agent_tool(self) -> None:
        assert constants.SPAN_AGENT_TOOL == "agent.tool"

    def test_span_agent_llm(self) -> None:
        assert constants.SPAN_AGENT_LLM == "agent.llm"


class TestExports:
    """Tests for __all__ exports."""

    def test_all_contains_version(self) -> None:
        assert "__version__" in constants.__all__

    def test_all_contains_env_constants(self) -> None:
        assert "ENV_PREFIX" in constants.__all__
        assert "ENV_NESTED_DELIMITER" in constants.__all__

    def test_all_contains_error_codes(self) -> None:
        assert "ERROR_AGENT_CONFIG" in constants.__all__
        assert "ERROR_AGENT_EXECUTION" in constants.__all__
        assert "ERROR_TOOL_NOT_FOUND" in constants.__all__
        assert "ERROR_TOOL_EXECUTION" in constants.__all__
        assert "ERROR_TOOL_ACCESS_DENIED" in constants.__all__
        assert "ERROR_MAX_ITERATIONS_EXCEEDED" in constants.__all__
        assert "ERROR_BUDGET_EXCEEDED" in constants.__all__

    def test_all_contains_metrics(self) -> None:
        assert "METRIC_AGENT_EXECUTIONS_TOTAL" in constants.__all__
        assert "METRIC_AGENT_EXECUTION_DURATION_MS" in constants.__all__

    def test_all_contains_spans(self) -> None:
        assert "SPAN_AGENT_EXECUTE" in constants.__all__
        assert "SPAN_AGENT_TOOL" in constants.__all__
        assert "SPAN_AGENT_LLM" in constants.__all__