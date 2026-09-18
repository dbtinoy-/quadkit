"""Tests for session contracts."""

import pytest
from datetime import datetime, timezone

from quadkit.contracts.ai.session import (
    SessionCheckpoint,
    SessionContextProtocol,
    SessionManagerProtocol,
    SessionState,
    SessionStatus,
    SessionStoreProtocol,
    SessionTurn,
)


class TestSessionDataclasses:
    """Test session dataclass definitions."""

    def test_session_status_enum(self) -> None:
        """SessionStatus should have expected values."""
        assert SessionStatus.ACTIVE.value == "active"
        assert SessionStatus.SUSPENDED.value == "suspended"
        assert SessionStatus.CLOSED.value == "closed"
        assert SessionStatus.EXPIRED.value == "expired"
        assert len(SessionStatus) == 4

    def test_session_turn_frozen(self) -> None:
        """SessionTurn should be frozen."""
        turn = SessionTurn(
            turn_id="1",
            role="user",
            content="hello",
            timestamp=datetime.now(timezone.utc),
        )
        with pytest.raises(AttributeError):
            turn.tokens_used = 100

    def test_session_turn_defaults(self) -> None:
        """SessionTurn should have proper defaults."""
        turn = SessionTurn(
            turn_id="1",
            role="user",
            content="hello",
            timestamp=datetime.now(timezone.utc),
        )
        assert turn.tool_calls == []
        assert turn.metadata == {}
        assert turn.tokens_used == 0
        assert turn.cost == 0.0

    def test_session_state_mutable(self) -> None:
        """SessionState should be mutable."""
        now = datetime.now(timezone.utc)
        state = SessionState(
            session_id="s1",
            user_id="u1",
            status=SessionStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        )
        # Should be able to mutate
        state.metadata["key"] = "value"
        assert state.metadata["key"] == "value"

    def test_session_state_defaults(self) -> None:
        """SessionState should have proper defaults."""
        state = SessionState(
            session_id="s1",
            user_id="u1",
            status=SessionStatus.ACTIVE,
        )
        assert state.turns == []
        assert state.active_tools == []
        assert state.checkpoint_id is None

    def test_session_checkpoint_frozen(self) -> None:
        """SessionCheckpoint should be frozen."""
        state = SessionState(
            session_id="s1",
            user_id="u1",
            status=SessionStatus.ACTIVE,
        )
        checkpoint = SessionCheckpoint(
            checkpoint_id="cp1",
            session_id="s1",
            state=state,
            created_at=datetime.now(timezone.utc),
        )
        with pytest.raises(AttributeError):
            checkpoint.checkpoint_id = "cp2"

    def test_session_checkpoint_defaults(self) -> None:
        """SessionCheckpoint should have proper defaults."""
        state = SessionState(
            session_id="s1",
            user_id="u1",
            status=SessionStatus.ACTIVE,
        )
        checkpoint = SessionCheckpoint(
            checkpoint_id="cp1",
            session_id="s1",
            state=state,
            created_at=datetime.now(timezone.utc),
        )
        assert checkpoint.parent_checkpoint_id is None
        assert checkpoint.metadata == {}


class TestSessionProtocols:
    """Test session protocols are runtime checkable."""

    def test_session_store_protocol_runtime_checkable(self) -> None:
        """SessionStoreProtocol should be runtime checkable."""
        assert isinstance(SessionStoreProtocol, type)

        class MockStore:
            async def save(self, state):
                pass

            async def load(self, session_id):
                return None

            async def delete(self, session_id):
                pass

            async def list_sessions(self, user_id):
                return []

            async def save_checkpoint(self, checkpoint):
                pass

            async def load_checkpoint(self, checkpoint_id):
                return None

            async def list_checkpoints(self, session_id):
                return []

            async def list_all_active(self):
                return []

        mock = MockStore()
        assert isinstance(mock, SessionStoreProtocol)

    def test_session_manager_protocol_runtime_checkable(self) -> None:
        """SessionManagerProtocol should be runtime checkable."""
        assert isinstance(SessionManagerProtocol, type)

        class MockManager:
            async def create(self, user_id, metadata=None):
                return SessionState(
                    session_id="s1",
                    user_id=user_id,
                    status=SessionStatus.ACTIVE,
                )

            async def resume(self, session_id):
                return None

            async def add_turn(self, session_id, turn):
                pass

            async def get_state(self, session_id):
                return None

            async def checkpoint(self, session_id):
                state = SessionState(
                    session_id=session_id,
                    user_id="u1",
                    status=SessionStatus.ACTIVE,
                )
                return SessionCheckpoint(
                    checkpoint_id="cp1",
                    session_id=session_id,
                    state=state,
                    created_at=datetime.now(timezone.utc),
                )

            async def restore(self, checkpoint_id):
                return SessionState(
                    session_id="s1",
                    user_id="u1",
                    status=SessionStatus.ACTIVE,
                )

            async def close(self, session_id):
                pass

            async def suspend(self, session_id):
                return SessionState(
                    session_id=session_id,
                    user_id="u1",
                    status=SessionStatus.SUSPENDED,
                )

        mock = MockManager()
        assert isinstance(mock, SessionManagerProtocol)

    def test_session_context_protocol_runtime_checkable(self) -> None:
        """SessionContextProtocol should be runtime checkable."""
        assert isinstance(SessionContextProtocol, type)

        state = SessionState(
            session_id="s1",
            user_id="u1",
            status=SessionStatus.ACTIVE,
        )

        class MockContext:
            @property
            def session_id(self):
                return "s1"

            @property
            def state(self):
                return state

            async def get_or_create(self, user_id):
                return state

        mock = MockContext()
        assert isinstance(mock, SessionContextProtocol)
