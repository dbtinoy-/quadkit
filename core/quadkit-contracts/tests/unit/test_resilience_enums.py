"""Tests for resilience enums."""

import pytest

from quadkit.contracts.infra.resilience.enums import CircuitState


class TestCircuitState:
    """Tests for CircuitState enum."""

    def test_closed_state(self) -> None:
        """Test closed state value."""
        assert CircuitState.CLOSED.value == "closed"

    def test_open_state(self) -> None:
        """Test open state value."""
        assert CircuitState.OPEN.value == "open"

    def test_half_open_state(self) -> None:
        """Test half_open state value."""
        assert CircuitState.HALF_OPEN.value == "half_open"

    def test_all_states_defined(self) -> None:
        """Test all circuit states are defined."""
        states = list(CircuitState)
        assert len(states) == 3
        assert CircuitState.CLOSED in states
        assert CircuitState.OPEN in states
        assert CircuitState.HALF_OPEN in states

    def test_state_is_string_enum(self) -> None:
        """Test that CircuitState is a string enum."""
        assert CircuitState.CLOSED == "closed"
        assert CircuitState.OPEN == "open"
        assert CircuitState.HALF_OPEN == "half_open"
