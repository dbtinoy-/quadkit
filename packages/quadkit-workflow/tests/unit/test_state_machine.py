"""Tests for state machine."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.contracts.workflow import StatePersistenceProtocol, StateTransitionRecord
from quadkit.workflow.state import (
    StateConcurrencyError,
    StateMachine,
    StateVersionConflictError,
)
from quadkit.workflow.state.models import State, Transition


class TestStateModels:
    """Tests for State and Transition models."""

    def test_state_creation(self) -> None:
        """Should create a state."""
        state = State("test_state")
        assert state.name == "test_state"
        assert state.transitions == {}

    def test_state_with_transitions(self) -> None:
        """Should create a state with transitions."""
        t = Transition("start", "running")
        state = State("idle", transitions={"start": t})
        assert "start" in state.transitions
        assert state.transitions["start"].target == "running"

    def test_transition_creation(self) -> None:
        """Should create a transition."""
        t = Transition("start", "running")
        assert t.event == "start"
        assert t.target == "running"

    def test_transition_with_guard(self) -> None:
        """Should create a transition with guard."""

        async def guard():
            return True

        t = Transition("start", "running", guard=guard)
        assert t.guard is not None

    def test_state_with_on_enter(self) -> None:
        """Should create a state with on_enter callback."""

        async def on_enter():
            pass

        state = State("running", on_enter=on_enter)
        assert state.on_enter is not None

    def test_state_with_on_exit(self) -> None:
        """Should create a state with on_exit callback."""

        async def on_exit():
            pass

        state = State("idle", on_exit=on_exit)
        assert state.on_exit is not None


class TestStateMachine:
    """Tests for state machine behavior."""

    def _make_states(self) -> list[State]:
        return [
            State("idle", transitions={"start": Transition("start", "running")}),
            State("running", transitions={"complete": Transition("complete", "done")}),
            State("done"),
        ]

    @pytest.mark.asyncio
    async def test_transition_persists_and_updates_version(self) -> None:
        """Should persist transitions and track version."""
        mock_persistence = MagicMock(spec=StatePersistenceProtocol)
        mock_persistence.append_transition = AsyncMock(return_value=1)

        machine = StateMachine(
            states=self._make_states(),
            initial_state="idle",
            persistence=mock_persistence,
            machine_id="order-1",
        )

        state = await machine.transition("start")

        assert state == "running"
        assert machine.current_state == "running"
        assert machine.version == 1
        mock_persistence.append_transition.assert_awaited_once_with(
            machine_id="order-1",
            from_state="idle",
            event="start",
            to_state="running",
            expected_version=0,
        )

    @pytest.mark.asyncio
    async def test_transition_raises_concurrency_error_on_conflict(self) -> None:
        """Typed conflict signal -> StateConcurrencyError, machine untouched."""
        mock_persistence = MagicMock(spec=StatePersistenceProtocol)
        mock_persistence.append_transition = AsyncMock(
            side_effect=StateVersionConflictError(
                "Optimistic lock failed: expected=0, actual=7",
                expected_version=0,
                actual_version=7,
            )
        )
        mock_persistence.get_current_version = AsyncMock(return_value=7)

        machine = StateMachine(
            states=self._make_states(),
            initial_state="idle",
            persistence=mock_persistence,
            machine_id="order-1",
        )

        with pytest.raises(StateConcurrencyError) as exc_info:
            await machine.transition("start")

        error = exc_info.value
        assert error.expected_version == 0
        assert error.actual_version == 7
        # The machine is left untouched: nothing ran before the CAS, so
        # there is no state or version to roll back.
        assert machine.current_state == "idle"
        assert machine.version == 0
        mock_persistence.get_current_version.assert_awaited_once_with("order-1")

    @pytest.mark.asyncio
    async def test_non_conflict_runtime_error_propagates_untouched(self) -> None:
        """A plain RuntimeError (driver/DDL failure) is NOT a version
        conflict: it propagates raw and the machine stays untouched."""
        mock_persistence = MagicMock(spec=StatePersistenceProtocol)
        mock_persistence.append_transition = AsyncMock(
            side_effect=RuntimeError("db connection lost")
        )
        mock_persistence.get_current_version = AsyncMock(return_value=7)

        machine = StateMachine(
            states=self._make_states(),
            initial_state="idle",
            persistence=mock_persistence,
            machine_id="order-1",
        )

        with pytest.raises(RuntimeError, match="db connection lost"):
            await machine.transition("start")

        assert machine.current_state == "idle"
        assert machine.version == 0
        # No spurious version re-read for a non-conflict failure.
        mock_persistence.get_current_version.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_conflict_executes_no_hooks(self) -> None:
        """A rejected transition must not run on_exit/on_enter side effects."""
        mock_persistence = MagicMock(spec=StatePersistenceProtocol)
        mock_persistence.append_transition = AsyncMock(
            side_effect=StateVersionConflictError(
                "Optimistic lock failed: expected=0, actual=1",
                expected_version=0,
                actual_version=1,
            )
        )
        mock_persistence.get_current_version = AsyncMock(return_value=1)

        exit_calls: list[str] = []
        enter_calls: list[str] = []

        async def on_exit() -> None:
            exit_calls.append("idle")

        async def on_enter() -> None:
            enter_calls.append("running")

        machine = StateMachine(
            states=[
                State("idle", transitions={"start": Transition("start", "running")}, on_exit=on_exit),
                State("running", on_enter=on_enter),
            ],
            initial_state="idle",
            persistence=mock_persistence,
            machine_id="order-1",
        )

        with pytest.raises(StateConcurrencyError):
            await machine.transition("start")

        assert exit_calls == []
        assert enter_calls == []
        assert machine.current_state == "idle"

    @pytest.mark.asyncio
    async def test_recover_rebuilds_state_and_version_from_persistence(self) -> None:
        """Should recover current state by replaying persisted transitions."""
        mock_persistence = MagicMock(spec=StatePersistenceProtocol)
        mock_persistence.load_transitions = AsyncMock(
            return_value=[
                StateTransitionRecord(
                    machine_id="order-1",
                    version=1,
                    from_state="idle",
                    event="start",
                    to_state="running",
                    transitioned_at=1.0,
                ),
                StateTransitionRecord(
                    machine_id="order-1",
                    version=2,
                    from_state="running",
                    event="complete",
                    to_state="done",
                    transitioned_at=2.0,
                ),
            ]
        )

        machine = StateMachine(
            states=self._make_states(),
            initial_state="idle",
            persistence=mock_persistence,
            machine_id="order-1",
        )

        recovered_state = await machine.recover()

        assert recovered_state == "done"
        assert machine.current_state == "done"
        assert machine.version == 2
        mock_persistence.load_transitions.assert_awaited_once_with("order-1")
