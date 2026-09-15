"""Tests for CLI types."""

import pytest
from enum import Enum

from quadkit.cli.types import CLIResult, CommandType


class TestCommandType:
    """Tests for CommandType enum."""

    def test_command_type_values(self) -> None:
        """Test all CommandType enum values."""
        assert CommandType.INIT.value == "init"
        assert CommandType.RUN.value == "run"
        assert CommandType.BUILD.value == "build"
        assert CommandType.GENERATE.value == "generate"

    def test_command_type_members(self) -> None:
        """Test CommandType has expected members."""
        members = list(CommandType)
        assert len(members) == 4
        assert CommandType.INIT in members
        assert CommandType.RUN in members
        assert CommandType.BUILD in members
        assert CommandType.GENERATE in members

    def test_command_type_enum(self) -> None:
        """Test CommandType is a proper enum."""
        assert issubclass(CommandType, Enum)

    def test_command_type_from_string(self) -> None:
        """Test creating CommandType from string."""
        assert CommandType("init") == CommandType.INIT
        assert CommandType("run") == CommandType.RUN
        assert CommandType("build") == CommandType.BUILD


class TestCLIResult:
    """Tests for CLIResult dataclass."""

    def test_success_result(self) -> None:
        """Test successful CLI result."""
        result = CLIResult(success=True, message="Operation completed")
        assert result.success is True
        assert result.message == "Operation completed"
        assert result.data is None

    def test_failure_result(self) -> None:
        """Test failure CLI result."""
        result = CLIResult(success=False, message="Operation failed")
        assert result.success is False
        assert result.message == "Operation failed"

    def test_result_with_data(self) -> None:
        """Test CLI result with data."""
        data = {"key": "value", "count": 42}
        result = CLIResult(success=True, message="Done", data=data)
        assert result.data == data
        assert result.data["key"] == "value"

    def test_result_default_values(self) -> None:
        """Test CLI result default values."""
        result = CLIResult(success=True)
        assert result.success is True
        assert result.message == ""
        assert result.data is None

    def test_result_dataclass(self) -> None:
        """Test CLIResult is a dataclass."""
        result1 = CLIResult(success=True, message="msg")
        result2 = CLIResult(success=True, message="msg")
        assert result1 == result2

    def test_types_exported(self) -> None:
        """Test that types are in __all__."""
        from quadkit.cli.types import __all__

        assert "CLIResult" in __all__
        assert "CommandType" in __all__
