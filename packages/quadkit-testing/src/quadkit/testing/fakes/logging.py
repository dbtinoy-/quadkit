"""Fake logger for capturing and asserting on log output in tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = ["FakeLogger", "LogEntry"]


@dataclass
class LogEntry:
    """A single captured log entry."""

    level: str
    message: str
    context: dict[str, Any] = field(default_factory=dict)


class FakeLogger:
    """Captures log entries for test assertions.

    Satisfies ``LoggerProtocol`` from ``quadkit.contracts.core.logging``.

    Example::

        logger = FakeLogger()
        logger.info("user_created", user_id="abc")
        logger.assert_logged("info", "user_created")
    """

    def __init__(self, bound_context: dict[str, Any] | None = None) -> None:
        self._entries: list[LogEntry] = []
        self._bound_context: dict[str, Any] = bound_context or {}

    # -- LoggerProtocol methods --------------------------------------------

    def debug(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Capture a DEBUG-level log entry."""
        self._log("debug", msg, kwargs)

    def info(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Capture an INFO-level log entry."""
        self._log("info", msg, kwargs)

    def warning(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Capture a WARNING-level log entry."""
        self._log("warning", msg, kwargs)

    def error(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Capture an ERROR-level log entry."""
        self._log("error", msg, kwargs)

    def critical(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Capture a CRITICAL-level log entry."""
        self._log("critical", msg, kwargs)

    def exception(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Capture an EXCEPTION-level log entry."""
        self._log("exception", msg, kwargs)

    def bind(self, **kwargs: Any) -> FakeLogger:
        """Return a new ``FakeLogger`` sharing entries with merged context."""
        child = FakeLogger(bound_context={**self._bound_context, **kwargs})
        child._entries = self._entries  # share the same list
        return child

    def unbind(self, *keys: str) -> FakeLogger:
        """Return a new ``FakeLogger`` with specified context keys removed."""
        new_ctx = {k: v for k, v in self._bound_context.items() if k not in keys}
        child = FakeLogger(bound_context=new_ctx)
        child._entries = self._entries
        return child

    # -- Query helpers -----------------------------------------------------

    @property
    def entries(self) -> list[LogEntry]:
        """All captured log entries."""
        return list(self._entries)

    # -- Assertion helpers -------------------------------------------------

    def assert_logged(self, level: str, msg_contains: str) -> None:
        """Assert that a log entry with *level* containing *msg_contains* exists."""
        for entry in self._entries:
            if entry.level == level and msg_contains in entry.message:
                return
        logged = [(e.level, e.message) for e in self._entries]
        msg = (
            f"Expected log entry at level={level!r} containing "
            f"{msg_contains!r} but found: {logged}"
        )
        raise AssertionError(msg)

    def assert_not_logged(
        self,
        level: str,
        msg_contains: str | None = None,
    ) -> None:
        """Assert no matching log entry exists."""
        for entry in self._entries:
            if entry.level != level:
                continue
            if msg_contains is None or msg_contains in entry.message:
                msg = (
                    f"Expected no log entry at level={level!r}"
                    + (f" containing {msg_contains!r}" if msg_contains else "")
                    + f" but found: ({entry.level}, {entry.message!r})"
                )
                raise AssertionError(msg)

    def clear(self) -> None:
        """Reset all captured entries."""
        self._entries.clear()

    # -- Internal ----------------------------------------------------------

    def _log(self, level: str, msg: str, extra: dict[str, Any]) -> None:
        context = {**self._bound_context, **extra}
        self._entries.append(LogEntry(level=level, message=msg, context=context))
