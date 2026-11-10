"""Tests for AI agents exceptions."""

import pytest

from quadkit.ai.agents.exceptions import (
    AgentConfigurationError,
    AgentExecutionError,
    BudgetExceededError,
    MaxIterationsExceededError,
    ToolAccessDeniedError,
    ToolExecutionError,
    ToolNotFoundError,
    ToolValidationError,
)


class TestAgentConfigurationError:
    """Tests for AgentConfigurationError."""

    def test_agent_configuration_error(self) -> None:
        """Test AgentConfigurationError basic."""
        error = AgentConfigurationError("Invalid config")
        assert "Invalid config" in str(error)

    def test_agent_configuration_error_omits_agent_identifier(self) -> None:
        """Agent identifiers are not exposed in serialized configuration errors."""
        private_agent = "private-agent-tenant-42"
        error = AgentConfigurationError(
            "Invalid config",
            agent_name=private_agent,
            details={"agent": private_agent},
        )
        assert private_agent not in str(error)
        assert private_agent not in repr(error.to_dict())
        assert "agent" not in error.details


class TestAgentExecutionError:
    """Tests for AgentExecutionError."""

    def test_agent_execution_error(self) -> None:
        """Test AgentExecutionError basic."""
        error = AgentExecutionError("Execution failed")
        assert "Execution failed" in str(error)

    def test_agent_execution_error_omits_agent_identifier(self) -> None:
        """Agent names are omitted while safe execution context is retained."""
        private_agent = "private-agent-tenant-42"
        error = AgentExecutionError(
            "Execution failed",
            agent_name=private_agent,
            step_number=5,
            details={"agent": private_agent},
        )
        assert error.details == {"step": 5}
        assert private_agent not in str(error)
        assert private_agent not in repr(error.to_dict())


class TestToolNotFoundError:
    """Tests for ToolNotFoundError."""

    def test_tool_not_found_error_omits_tool_identifiers(self) -> None:
        """Tool names and the available-tool list are not serialized."""
        private_tool = "private-tool-tenant-42"
        private_available = ["private-tool-a", "private-tool-b"]
        error = ToolNotFoundError(
            tool_name=private_tool,
            available_tools=private_available,
            details={"tool": private_tool, "available": private_available},
        )
        serialized = repr(error.to_dict())
        assert private_tool not in str(error)
        assert private_tool not in serialized
        assert all(name not in serialized for name in private_available)
        assert error.details == {}


class TestToolExecutionError:
    """Tests for ToolExecutionError."""

    def test_tool_execution_error_omits_identifiers_and_arguments(self) -> None:
        """Tool names and raw arguments are not serialized in execution errors."""
        private_tool = "private-tool-tenant-42"
        private_argument = "token=secret at /srv/private/tenant-42"
        error = ToolExecutionError(
            tool_name=private_tool,
            arguments={"query": private_argument},
            details={
                "tool": private_tool,
                "arguments": {"query": private_argument},
            },
        )
        serialized = repr(error.to_dict())
        assert private_tool not in str(error)
        assert private_argument not in str(error)
        assert private_tool not in serialized
        assert private_argument not in serialized
        assert error.details == {}


class TestToolAccessDeniedError:
    """Tests for ToolAccessDeniedError."""

    def test_tool_access_denied_error_omits_tool_and_module_identifiers(self) -> None:
        """Access-control errors do not reveal internal tool/module names."""
        private_ids = (
            "private-tool-tenant-42",
            "private-agent-module-42",
            "private-tool-module-42",
        )
        error = ToolAccessDeniedError(
            tool_name=private_ids[0],
            agent_module=private_ids[1],
            tool_module=private_ids[2],
            details={
                "tool": private_ids[0],
                "agent_module": private_ids[1],
                "tool_module": private_ids[2],
            },
        )
        serialized = repr(error.to_dict())
        assert all(identifier not in str(error) for identifier in private_ids)
        assert all(identifier not in serialized for identifier in private_ids)
        assert error.details == {}


class TestMaxIterationsExceededError:
    """Tests for MaxIterationsExceededError."""

    def test_max_iterations_exceeded_error(self) -> None:
        """Test MaxIterationsExceededError basic."""
        error = MaxIterationsExceededError()
        assert "Maximum iterations exceeded" in str(error)

    def test_max_iterations_exceeded_error_details(self) -> None:
        """Test MaxIterationsExceededError with iteration details."""
        error = MaxIterationsExceededError(
            max_iterations=10,
            current_iteration=10,
        )
        assert error.details.get("max_iterations") == 10
        assert error.details.get("current_iteration") == 10


class TestBudgetExceededError:
    """Tests for BudgetExceededError."""

    def test_budget_exceeded_error(self) -> None:
        """Test BudgetExceededError basic."""
        error = BudgetExceededError()
        assert "Budget exceeded" in str(error)

    def test_budget_exceeded_error_details(self) -> None:
        """Test BudgetExceededError with budget details."""
        error = BudgetExceededError(
            budget_type="tokens",
            limit=1000,
            used=1100,
        )
        assert error.details.get("budget_type") == "tokens"
        assert error.details.get("limit") == 1000
        assert error.details.get("used") == 1100


class TestToolValidationError:
    """Tests for ToolValidationError."""

    def test_tool_validation_error(self) -> None:
        """Test ToolValidationError basic."""
        error = ToolValidationError()
        assert "Tool input validation failed" in str(error)

    def test_tool_validation_error_omits_identifiers(self) -> None:
        """Tool and schema-field identifiers are not serialized."""
        private_tool = "private-tool-tenant-42"
        private_field = "private/customer/identifier"
        error = ToolValidationError(
            tool_name=private_tool,
            field=private_field,
            details={"tool": private_tool, "field": private_field},
        )
        serialized = repr(error.to_dict())
        assert private_tool not in str(error)
        assert private_field not in str(error)
        assert private_tool not in serialized
        assert private_field not in serialized
        assert error.details == {}
