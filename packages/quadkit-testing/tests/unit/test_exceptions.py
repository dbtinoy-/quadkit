"""Tests for testing exceptions."""

import pytest

from quadkit.testing.exceptions import TestingError, TokenBudgetExceededError


class TestTestingError:
    """Tests for TestingError."""

    def test_testing_error_is_quadkit_error(self) -> None:
        """Test TestingError inherits from QuadkitError."""
        error = TestingError("Test error")
        from quadkit.contracts.exceptions import QuadkitError

        assert isinstance(error, QuadkitError)


class TestTokenBudgetExceededError:
    """Tests for TokenBudgetExceededError."""

    def test_token_budget_exceeded_error_attributes(self) -> None:
        """Test TokenBudgetExceededError stores token information."""
        error = TokenBudgetExceededError(tokens_used=1000, token_budget=2000)

        assert error.tokens_used == 1000
        assert error.token_budget == 2000

    def test_token_budget_exceeded_error_message(self) -> None:
        """Test TokenBudgetExceededError message contains token info."""
        error = TokenBudgetExceededError(tokens_used=1500, token_budget=2000)

        assert "1500" in str(error)
        assert "2000" in str(error)

    def test_token_budget_exceeded_error_hint(self) -> None:
        """Test TokenBudgetExceededError includes hint."""
        error = TokenBudgetExceededError(tokens_used=1500, token_budget=2000)

        assert "max_tokens_per_run" in str(error)
