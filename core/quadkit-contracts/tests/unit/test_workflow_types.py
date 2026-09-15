"""Tests for workflow types."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from quadkit.contracts.workflow.types import StateTransitionRecord


class TestStateTransitionRecord:
    """Tests for StateTransitionRecord."""

    def test_creation(self) -> None:
        """Test creating a StateTransitionRecord."""
        record = StateTransitionRecord(
            machine_id="machine-123",
            version=1,
            from_state="pending",
            event="approve",
            to_state="approved",
            transitioned_at=1700000000.0,
        )
        assert record.machine_id == "machine-123"
        assert record.version == 1
        assert record.from_state == "pending"
        assert record.event == "approve"
        assert record.to_state == "approved"
        assert record.transitioned_at == 1700000000.0

    def test_frozen_dataclass(self) -> None:
        """Test StateTransitionRecord is frozen (immutable)."""
        record = StateTransitionRecord(
            machine_id="machine-123",
            version=1,
            from_state="pending",
            event="approve",
            to_state="approved",
            transitioned_at=1700000000.0,
        )
        with pytest.raises(FrozenInstanceError):
            record.version = 2

    def test_version_increments(self) -> None:
        """Test version is used for optimistic locking."""
        record1 = StateTransitionRecord(
            machine_id="machine-123",
            version=1,
            from_state="pending",
            event="approve",
            to_state="approved",
            transitioned_at=1700000000.0,
        )
        record2 = StateTransitionRecord(
            machine_id="machine-123",
            version=2,
            from_state="approved",
            event="complete",
            to_state="completed",
            transitioned_at=1700000001.0,
        )
        assert record1.version < record2.version

    def test_can_use_in_list(self) -> None:
        """Test StateTransitionRecord can be stored in a list."""
        history = [
            StateTransitionRecord(
                machine_id="machine-123",
                version=1,
                from_state="pending",
                event="start",
                to_state="running",
                transitioned_at=1700000000.0,
            ),
            StateTransitionRecord(
                machine_id="machine-123",
                version=2,
                from_state="running",
                event="complete",
                to_state="done",
                transitioned_at=1700000001.0,
            ),
        ]
        assert len(history) == 2
        assert history[0].version == 1
        assert history[1].version == 2

    def test_can_compare_states(self) -> None:
        """Test can compare from_state and to_state."""
        record = StateTransitionRecord(
            machine_id="machine-123",
            version=1,
            from_state="draft",
            event="publish",
            to_state="published",
            transitioned_at=1700000000.0,
        )
        assert record.from_state == "draft"
        assert record.to_state == "published"
        assert record.from_state != record.to_state


class TestStateTransitionRecordIntegration:
    """Integration tests for StateTransitionRecord."""

    def test_can_reconstruct_from_event(self) -> None:
        """Test reconstructing transition from event data."""
        event_data = {
            "machine_id": "order-456",
            "version": 3,
            "from_state": "payment_pending",
            "event": "payment_received",
            "to_state": "processing",
            "transitioned_at": 1700000000.0,
        }
        record = StateTransitionRecord(**event_data)
        assert record.machine_id == "order-456"
        assert record.event == "payment_received"

    def test_can_use_in_state_machine_simulation(self) -> None:
        """Test using StateTransitionRecord in state machine logic."""
        transitions = []

        for idx, (event, new_state) in enumerate(
            [
                ("create", "created"),
                ("process", "processing"),
                ("complete", "completed"),
            ],
            start=1,
        ):
            old_state = "pending" if idx == 1 else "processing"
            if idx == 3:
                old_state = "processing"

            transitions.append(
                StateTransitionRecord(
                    machine_id="order-789",
                    version=idx,
                    from_state=old_state,
                    event=event,
                    to_state=new_state,
                    transitioned_at=1700000000.0 + idx,
                )
            )

        assert len(transitions) == 3
        assert transitions[2].to_state == "completed"
