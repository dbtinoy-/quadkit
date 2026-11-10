"""Tests for workflow types."""

import pytest

from quadkit.workflow.bulk import BulkOperationState


class TestBulkOperationState:
    """Tests for BulkOperationState enum."""

    def test_has_pending_state(self) -> None:
        """Should have PENDING state."""
        assert BulkOperationState.PENDING is not None
