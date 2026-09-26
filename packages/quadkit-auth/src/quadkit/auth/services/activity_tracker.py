"""In-process tracker for auth activity (failed logins, token refreshes).

Bounded ring buffers with wall-clock windows. Counters are real runtime
observations written by the login and JWT-lifecycle paths.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
import threading
import time

_MAX_EVENTS = 10_000


class AuthActivityTracker:
    """Thread-safe, bounded tracker of auth events."""

    def __init__(
        self,
        max_events: int = _MAX_EVENTS,
        window_size_seconds: int = 3600,
        now: Callable[[], float] | None = None,
    ) -> None:
        """Initialize the tracker.

        Args:
            max_events: Maximum buffered events per stream before pruning.
            window_size_seconds: Retention window for buffered events.
            now: Clock function returning seconds; defaults to ``time.monotonic``.
        """
        self._max_events = max_events
        self._window_size = window_size_seconds
        self._now = now or time.monotonic
        self._failures: deque[tuple[float, str]] = deque()
        self._refreshes: deque[float] = deque()
        self._lock = threading.Lock()

    def record_failed_login(self, ip: str = "unknown") -> None:
        """Record one failed login attempt from ``ip``.

        Args:
            ip: Client IP when known; defaults to ``"unknown"`` for auth
                paths that carry no request context.
        """
        with self._lock:
            self._failures.append((self._now(), ip))
            self._prune(self._failures, self._now() - self._window_size)

    def record_refresh(self) -> None:
        """Record one token refresh."""
        with self._lock:
            self._refreshes.append(self._now())
            self._prune(self._refreshes, self._now() - self._window_size)

    def failed_login_summary(self, window_minutes: int) -> tuple[int, int]:
        """Return ``(count, unique_ips)`` for the last ``window_minutes``.

        Args:
            window_minutes: Look-back window in minutes.

        Returns:
            Tuple of failure count and distinct source IPs.
        """
        cutoff = self._now() - window_minutes * 60
        with self._lock:
            recent = [ip for ts, ip in self._failures if ts >= cutoff]
        return len(recent), len(set(recent))

    def refresh_summary(self, window_minutes: int) -> tuple[float, int]:
        """Return ``(rate_per_minute, total)`` for the last ``window_minutes``.

        Args:
            window_minutes: Look-back window in minutes.

        Returns:
            Tuple of refreshes-per-minute and total refresh count.
        """
        cutoff = self._now() - window_minutes * 60
        with self._lock:
            recent = [ts for ts in self._refreshes if ts >= cutoff]
        minutes = max(window_minutes, 1)
        return round(len(recent) / minutes, 1), len(recent)

    def _prune(self, buffer: deque, cutoff: float, key: int = 0) -> None:
        """Drop entries older than ``cutoff`` and over the size bound."""
        while buffer:
            entry = buffer[0]
            value = entry[key] if isinstance(entry, tuple) else entry
            if value >= cutoff:
                break
            buffer.popleft()
        while len(buffer) > self._max_events:
            buffer.popleft()


__all__ = ["AuthActivityTracker"]
