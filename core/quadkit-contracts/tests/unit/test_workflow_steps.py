"""Unit tests for quadkit.contracts.workflow.steps module."""

from __future__ import annotations

import pytest

from quadkit.contracts.workflow import SagaStepError


class TestSagaStepError:
    """Tests for SagaStepError exception."""

    def test_create_with_detail_only(self) -> None:
        """Verify SagaStepError with only detail."""
        error = SagaStepError("Something went wrong")
        assert error.detail == "Something went wrong"
        assert error.step_name == ""
        assert str(error) == "Something went wrong"

    def test_create_with_detail_and_step_name(self) -> None:
        """Verify SagaStepError with detail and step_name."""
        error = SagaStepError("Payment failed", step_name="process_payment")
        assert error.detail == "Payment failed"
        assert error.step_name == "process_payment"

    def test_repr_includes_step_and_detail(self) -> None:
        """Verify __repr__ includes step and detail."""
        error = SagaStepError("Error message", step_name="my_step")
        repr_str = repr(error)
        assert "SagaStepError" in repr_str
        assert "my_step" in repr_str
        assert "Error message" in repr_str

    def test_is_exception_subclass(self) -> None:
        """Verify SagaStepError is an Exception subclass."""
        error = SagaStepError("test")
        assert isinstance(error, Exception)

    def test_can_be_caught(self) -> None:
        """Verify SagaStepError can be caught."""
        with pytest.raises(SagaStepError):
            raise SagaStepError("test error")

    def test_default_step_name_is_empty_string(self) -> None:
        """Verify default step_name is empty string."""
        error = SagaStepError("detail")
        assert error.step_name == ""

    def test_args_contains_detail(self) -> None:
        """Verify args contains the detail message."""
        error = SagaStepError("my error")
        assert "my error" in error.args