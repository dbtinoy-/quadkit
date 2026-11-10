"""Tests for workflow exceptions."""

import pytest

from quadkit.workflow.bulk import (
    BulkOperationCancelledError,
    BulkOperationError,
    BulkOperationTimeoutError,
)
from quadkit.workflow.saga.base import SagaError
from quadkit.workflow.state.exceptions import StateError


class TestBulkOperationError:
    """Tests for BulkOperationError."""

    def test_can_instantiate(self) -> None:
        """Should be able to create an error."""
        error = BulkOperationError("test")
        assert "test" in str(error)


class TestBulkOperationTimeoutError:
    """Tests for BulkOperationTimeoutError."""

    def test_can_instantiate(self) -> None:
        """Should be able to create an error."""
        error = BulkOperationTimeoutError("timeout")
        assert "timeout" in str(error)


class TestBulkOperationCancelledError:
    """Tests for BulkOperationCancelledError."""

    def test_can_instantiate(self) -> None:
        """Should be able to create an error."""
        error = BulkOperationCancelledError("cancelled")
        assert "cancelled" in str(error)
