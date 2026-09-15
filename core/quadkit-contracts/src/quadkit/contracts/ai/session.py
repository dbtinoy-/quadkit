"""Session management contracts for stateful conversations."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from typing_extensions import Protocol, runtime_checkable

from quadkit.contracts.exceptions import QuadkitError

if TYPE_CHECKING:
    from quadkit.contracts.ai.llm import ChatMessageProtocol


# Session Errors
class SessionError(QuadkitError):
    """Base class for session-related errors."""

    _code = "QK_ERR_SES_001"


class TaskCancelledError(QuadkitError):
    """Error raised when a task is cancelled."""

    _code = "QK_ERR_SES_002"


class TaskError(QuadkitError):
    """Base class for task execution errors."""

    _code = "QK_ERR_SES_003"


class TaskTimeoutError(TaskError):
    """Error raised when a task times out."""

    _code = "QK_ERR_SES_004"


class TaskValidationError(TaskError):
    """Error raised when task input validation fails."""

    _code = "QK_ERR_SES_005"


class SessionStatus(StrEnum):
    """Status of a conversation session.

    Attributes:
        ACTIVE: Session is currently active
        SUSPENDED: Session is paused but can be resumed
        CLOSED: Session has been terminated
        EXPIRED: Session has expired due to TTL
    """

    ACTIVE = "active"
    SUSPENDED = "suspended"
    CLOSED = "closed"
    EXPIRED = "expired"


@dataclass(frozen=True)
class SessionTurn:
    """A single turn (exchange) in a conversation session.

    Attributes:
        turn_id: Unique ID for this turn
        role: The role (e.g., "user", "assistant", "system", "tool")
        content: The content of this turn
        timestamp: When this turn occurred
        tool_calls: List of tool calls made during this turn
        skill_results: Results from skill executions in this turn
        metadata: Additional metadata about the turn
        tokens_used: Tokens consumed by this turn
        cost: If metered, cost of this turn
        model: Model that produced this turn (if applicable)
        provider: Provider that served this turn (if applicable)
    """

    turn_id: str
    role: str
    content: str
    timestamp: datetime
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    skill_results: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    tokens_used: int = 0
    cost: float = 0.0
    model: str | None = None
    provider: str | None = None


@dataclass(frozen=True)
class SessionState:
    """Complete state of a conversation session.

    Frozen dataclass representing the current state of a session,
    including all turns and metadata. List and dict fields are frozen
    by reference — their contents remain mutable where needed.

    Attributes:
        session_id: Unique session identifier
        user_id: User who owns this session
        status: Current session status
        turns: All turns in this session
        metadata: Session-level metadata
        active_tools: Tools currently active in this session
        active_skills: Skills currently active in this session
        system_prompt: Optional system prompt for this session
        variables: User-defined session-level variables
        created_at: When session was created
        updated_at: When session was last modified
        checkpoint_id: ID of last checkpoint (if any)
        total_tokens: Cumulative tokens used across all turns
        total_cost: Cumulative cost across all turns
        turn_count: Number of turns recorded
        parent_session_id: Parent session ID if this is a branch
        branch_name: Name of this branch if forked
    """

    session_id: str
    user_id: str
    status: SessionStatus
    turns: list[SessionTurn] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    active_tools: list[str] = field(default_factory=list)
    active_skills: list[str] = field(default_factory=list)
    system_prompt: str | None = None
    variables: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    checkpoint_id: str | None = None
    total_tokens: int = 0
    total_cost: float = 0.0
    turn_count: int = 0
    parent_session_id: str | None = None
    branch_name: str | None = None


@dataclass(frozen=True)
class SessionCheckpoint:
    """A snapshot of session state at a point in time.

    Immutable checkpoint that can be used for restoring session state
    or implementing branching/versioning.

    Attributes:
        checkpoint_id: Unique identifier for this checkpoint
        session_id: ID of the session this checkpoint belongs to
        state: The complete session state at checkpoint time
        created_at: When this checkpoint was created
        parent_checkpoint_id: ID of the parent checkpoint (for DAG tracking)
        metadata: Optional checkpoint metadata
    """

    checkpoint_id: str
    session_id: str
    state: SessionState
    created_at: datetime
    parent_checkpoint_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class SessionStoreProtocol(Protocol):
    """Protocol for storing and retrieving session state.

    Implementations provide persistence for session state, supporting
    creation, loading, deletion, and enumeration of sessions.
    """

    async def save(self, state: SessionState) -> None:
        """Save or update a session state.

        Args:
            state: The session state to save
        """
        ...

    async def load(self, session_id: str) -> SessionState | None:
        """Load a session state by ID.

        Args:
            session_id: The session ID to load

        Returns:
            The session state, or None if not found
        """
        ...

    async def delete(self, session_id: str) -> None:
        """Delete a session.

        Args:
            session_id: The session ID to delete
        """
        ...

    async def list_sessions(self, user_id: str) -> list[SessionState]:
        """List all sessions for a user.

        Args:
            user_id: The user ID to query

        Returns:
            List of sessions owned by this user
        """
        ...

    async def save_checkpoint(self, checkpoint: SessionCheckpoint) -> None:
        """Persist an immutable session checkpoint.

        Args:
            checkpoint: The checkpoint to save.
        """
        ...

    async def load_checkpoint(self, checkpoint_id: str) -> SessionCheckpoint | None:
        """Load a checkpoint by ID.

        Args:
            checkpoint_id: The checkpoint ID to load.

        Returns:
            The checkpoint, or None if not found.
        """
        ...

    async def list_checkpoints(self, session_id: str) -> list[SessionCheckpoint]:
        """List all checkpoints for a session.

        Args:
            session_id: The session to list checkpoints for.

        Returns:
            All checkpoints in chronological order.
        """
        ...

    async def list_all_active(self) -> list[SessionState]:
        """List every non-closed session across all users.

        Intended for maintenance tooling (e.g. TTL cleanup schedulers)
        that must scan sessions without knowing the owning users.

        Returns:
            All sessions whose status is not closed.
        """
        ...


@runtime_checkable
class SessionManagerProtocol(Protocol):
    """Protocol for managing session lifecycle.

    Handles session creation, resumption, state management,
    checkpointing, and restoration.
    """

    async def create(
        self, user_id: str, metadata: dict[str, Any] | None = None
    ) -> SessionState:
        """Create a new session.

        Args:
            user_id: The user ID
            metadata: Optional session metadata

        Returns:
            The newly created session
        """
        ...

    async def resume(self, session_id: str) -> SessionState | None:
        """Resume an existing session.

        Args:
            session_id: The session ID to resume

        Returns:
            The session state, or None if not found or closed
        """
        ...

    async def add_turn(self, session_id: str, turn: SessionTurn) -> None:
        """Add a turn to a session.

        Args:
            session_id: The session to update
            turn: The turn to add
        """
        ...

    async def get_state(self, session_id: str) -> SessionState | None:
        """Get the current state of a session.

        Args:
            session_id: The session ID

        Returns:
            The session state, or None if not found
        """
        ...

    async def checkpoint(self, session_id: str) -> SessionCheckpoint:
        """Create a checkpoint of the session.

        Args:
            session_id: The session to checkpoint

        Returns:
            The created checkpoint
        """
        ...

    async def restore(self, checkpoint_id: str) -> SessionState:
        """Restore session state from a checkpoint.

        Args:
            checkpoint_id: The checkpoint ID to restore from

        Returns:
            The restored session state
        """
        ...

    async def close(self, session_id: str) -> None:
        """Close/terminate a session.

        Args:
            session_id: The session to close
        """
        ...

    async def suspend(self, session_id: str) -> SessionState:
        """Suspend an active session without closing it.

        Args:
            session_id: The session to suspend.

        Returns:
            Updated session state with status ``suspended``.
        """
        ...


@runtime_checkable
class SessionContextProtocol(Protocol):
    """Protocol for per-request session context.

    Provides access to the current session within a request scope,
    with ability to bind and retrieve session state.
    """

    @property
    def session_id(self) -> str:
        """Get the current session ID.

        Returns:
            The current session ID

        Raises:
            SessionError: If no session is currently bound
        """
        ...

    @property
    def state(self) -> SessionState:
        """Get the current session state.

        Returns:
            The current session state

        Raises:
            SessionError: If no session is currently bound
        """
        ...

    async def get_or_create(self, user_id: str) -> SessionState:
        """Get an existing session or create a new one.

        Args:
            user_id: The user ID

        Returns:
            An existing or newly created session
        """
        ...


@runtime_checkable
class ContextPrunerProtocol(Protocol):
    """Relevance-based conversation history pruning.

    Unlike sliding-window truncation, implementations score each turn for
    relevance to the current query and preserve high-value turns regardless
    of their position in the history.
    """

    async def prune(
        self,
        history: Sequence[ChatMessageProtocol],
        current_query: str,
        max_turns: int,
    ) -> list[ChatMessageProtocol]:
        """Prune history to at most max_turns, preserving relevant turns.

        Args:
            history: Full conversation history as ChatMessageProtocol instances.
            current_query: The current user query (used for relevance scoring).
            max_turns: Maximum number of turns to retain.

        Returns:
            Pruned history in chronological order.
        """
        ...


__all__ = [
    "ContextPrunerProtocol",
    "SessionCheckpoint",
    "SessionContextProtocol",
    "SessionError",
    "SessionManagerProtocol",
    "SessionState",
    "SessionStatus",
    "SessionStoreProtocol",
    "SessionTurn",
    "TaskCancelledError",
    "TaskError",
    "TaskTimeoutError",
    "TaskValidationError",
]
