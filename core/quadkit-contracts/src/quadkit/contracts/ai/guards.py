"""AI guard chain protocols for input/output policy enforcement."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from quadkit.contracts.ai.exceptions import GuardError

if TYPE_CHECKING:
    from quadkit.contracts.core.result import Result


# Guard Errors
class InputGuardError(GuardError):
    """Error raised during input guard validation."""

    _code = "QK_ERR_GUARD_002"


class OutputGuardError(GuardError):
    """Error raised during output guard validation."""

    _code = "QK_ERR_GUARD_003"


@runtime_checkable
class GuardResultProtocol(Protocol):
    """Protocol for guard evaluation results.

    Every guard returns a result indicating whether the content
    passed, was blocked, or triggered a warning.
    """

    @property
    def passed(self) -> bool:
        """Whether the guard check passed."""
        ...

    @property
    def action(self) -> str:
        """Action taken: 'pass', 'block', 'warn', or 'redact'."""
        ...

    @property
    def guard_name(self) -> str:
        """Name of the guard that produced this result."""
        ...

    @property
    def details(self) -> dict[str, Any]:
        """Additional details about the guard evaluation."""
        ...

    @property
    def redacted_content(self) -> str | None:
        """Redacted content, if action was 'redact'."""
        ...


@runtime_checkable
class InputGuardProtocol(Protocol):
    """Protocol for input content guards.

    Input guards inspect user prompts and messages before they are
    sent to an LLM.  They can block, warn, or redact content.
    """

    @property
    def name(self) -> str:
        """GuardProtocol identifier."""
        ...

    async def check(
        self,
        content: str,
        *,
        messages: list[Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Result[GuardResultProtocol, GuardError]:
        """Evaluate input content against this guard's rules.

        Args:
            content: The raw text content to check.
            messages: Optional structured message list for context.
            metadata: Optional metadata (user_id, model, etc.).

        Returns:
            A GuardCheckResult indicating pass/block/warn/redact.
        """
        ...


@runtime_checkable
class OutputGuardProtocol(Protocol):
    """Protocol for output content guards.

    Output guards inspect LLM responses before they are returned
    to the caller.  They can block, warn, or redact content.
    """

    @property
    def name(self) -> str:
        """GuardProtocol identifier."""
        ...

    async def check(
        self,
        content: str,
        *,
        original_input: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Result[GuardResultProtocol, GuardError]:
        """Evaluate output content against this guard's rules.

        Args:
            content: The LLM response text to check.
            original_input: The original user input for context.
            metadata: Optional metadata (model, provider, etc.).

        Returns:
            A GuardCheckResult indicating pass/block/warn/redact.
        """
        ...


@runtime_checkable
class GuardPipelineProtocol(Protocol):
    """Protocol for guard pipeline execution.

    Orchestrates a chain of input and/or output guards, collecting
    results and determining the aggregate action.
    """

    async def check_input(
        self,
        content: str,
        *,
        messages: list[Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Result[GuardResultProtocol, GuardError]:
        """Run all input guards against the content.

        Args:
            content: Input text to guard.
            messages: Optional structured messages.
            metadata: Optional request metadata.

        Returns:
            Aggregate guard result.
        """
        ...

    async def check_output(
        self,
        content: str,
        *,
        original_input: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Result[GuardResultProtocol, GuardError]:
        """Run all output guards against the content.

        Args:
            content: Output text to guard.
            original_input: The original user input.
            metadata: Optional request metadata.

        Returns:
            Aggregate guard result.
        """
        ...


__all__ = [
    "GuardError",
    "GuardPipelineProtocol",
    "GuardResultProtocol",
    "InputGuardError",
    "InputGuardProtocol",
    "OutputGuardError",
    "OutputGuardProtocol",
]
