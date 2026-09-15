"""Tests for mapping exceptions."""

from quadkit.mapping.exceptions import (
    MappingError,
    MappingExecutionError,
    MappingNotFoundError,
)


class TestMappingError:
    """Tests for MappingError."""

    def test_mapping_error(self) -> None:
        """Should instantiate."""
        error = MappingError("Mapping error")
        assert "Mapping error" in str(error)


class TestMappingNotFoundError:
    """Tests for MappingNotFoundError."""

    def test_mapping_not_found_error(self) -> None:
        """Should instantiate with types."""
        error = MappingNotFoundError(str, int)
        assert "No mapper registered" in str(error)
        assert error.source is str
        assert error.dest is int


class TestMappingExecutionError:
    """Tests for MappingExecutionError."""

    def test_mapping_execution_error(self) -> None:
        """Should instantiate."""
        error = MappingExecutionError("Mapping execution failed")
        assert "Mapping execution failed" in str(error)
