"""Optional external error tracking integration (Sentry).

Error tracking is gated entirely by :attr:`ErrorTrackingConfig.dsn` (env:
``QK_MONITOR__ERROR_TRACKING__DSN``).  When no DSN is configured a
:class:`NullErrorTracker` is returned and the integration is a no-op.  When a
DSN is configured but ``sentry-sdk`` is not installed, setup degrades to the
no-op tracker with a warning instead of raising.

Example:
    ```python
    from quadkit.monitor.config import ErrorTrackingConfig
    from quadkit.monitor.error_tracking import setup_error_tracking

    tracker = setup_error_tracking(ErrorTrackingConfig(dsn="https://key@sentry.io/1"))
    try:
        ...
    except Exception as exc:
        tracker.capture_exception(exc)
    tracker.flush()
    ```
"""

from __future__ import annotations

import os
import sys
from typing import Any, Protocol, runtime_checkable

import structlog

from quadkit.logging import get_logger
from quadkit.monitor.config import ErrorTrackingConfig
from quadkit.validation import SecretStr

logger = get_logger(__name__)


@runtime_checkable
class ErrorTrackerProtocol(Protocol):
    """Minimal interface for capturing exceptions to an external service."""

    def capture_exception(self, exc: BaseException) -> None:
        """Report an exception to the external error tracking service."""

    def flush(self, timeout: float = 2.0) -> None:
        """Flush buffered events to the external service.

        Args:
            timeout: Max seconds to wait for delivery.
        """


class NullErrorTracker:
    """No-op tracker used when no DSN is configured.

    Keeps capture/flush calls safe so callers never need to branch on
    whether error tracking is active.
    """

    def capture_exception(self, exc: BaseException) -> None:
        """Log the exception locally instead of reporting it externally."""
        logger.debug("error_tracking_noop", error=str(exc))

    def flush(self, timeout: float = 2.0) -> None:
        """Nothing to flush."""


_SENSITIVE_MARKERS = (
    "password",
    "passwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "authorization",
    "credential",
    "private_key",
    "dsn",
)


def _scrub_event(event: dict, hint: Any) -> dict:
    """Mask denylisted keys in an outbound Sentry event payload.

    Walks ``request.headers`` / ``request.data`` / ``extra`` and masks any
    key containing a sensitive marker so credentials never leave the process.
    """

    def _walk(node: object) -> None:
        if isinstance(node, dict):
            for key in list(node):
                if isinstance(key, str) and any(
                    marker in key.lower() for marker in _SENSITIVE_MARKERS
                ):
                    node[key] = "[redacted]"
                else:
                    _walk(node[key])
        elif isinstance(node, (list, tuple)):
            for item in node:
                _walk(item)

    _walk(event)
    return event


class SentryErrorTracker:
    """Sentry-backed tracker used when a DSN is configured."""

    def __init__(
        self, config: ErrorTrackingConfig, sentry: Any, dsn: str | None = None
    ) -> None:
        """Initialize the Sentry SDK.

        Args:
            config: Error tracking config with a non-empty ``dsn``.
            sentry: Imported ``sentry_sdk`` module.
            dsn: Effective DSN to use; falls back to ``config.dsn`` when unset.
        """
        self._config = config
        self._sentry = sentry
        effective_dsn = dsn
        if effective_dsn is None and isinstance(config.dsn, SecretStr):
            effective_dsn = config.dsn.get_secret_value()
        sentry.init(
            dsn=effective_dsn,
            environment=config.environment,
            traces_sample_rate=config.traces_sample_rate,
            send_default_pii=config.send_default_pii,
            before_send=_scrub_event,
        )

    def capture_exception(self, exc: BaseException) -> None:
        """Report the exception to Sentry."""
        self._sentry.capture_exception(exc)

    def flush(self, timeout: float = 2.0) -> None:
        """Flush buffered events to Sentry.

        Args:
            timeout: Max seconds to wait for delivery.
        """
        self._sentry.flush(timeout=timeout)


def setup_error_tracking(config: ErrorTrackingConfig) -> ErrorTrackerProtocol:
    """Initialize error tracking from config; no-op when no DSN is set.

    Args:
        config: Error tracking configuration.  When ``dsn`` is unset or
            blank, a :class:`NullErrorTracker` is returned and no external
            connection is attempted.

    Returns:
        An active tracker when the DSN is set and ``sentry-sdk`` is
        installed, otherwise a no-op :class:`NullErrorTracker`.

    Example:
        ```python
        tracker = setup_error_tracking(MonitorConfig().error_tracking)
        ```
    """
    configured: str | None = (
        config.dsn.get_secret_value()
        if isinstance(config.dsn, SecretStr)
        else config.dsn
    )
    dsn: str | None = configured or os.getenv("SENTRY_DSN")
    if not dsn or not dsn.strip():
        return NullErrorTracker()
    try:
        import sentry_sdk
    except ImportError:
        logger.warning(
            "error_tracking_skipped",
            reason="sentry-sdk is not installed",
            detail="Install sentry-sdk or quadkit-monitor extras to enable error tracking",
        )
        return NullErrorTracker()
    return SentryErrorTracker(config, sentry_sdk, dsn=dsn)


class UnhandledExceptionHook:
    """``sys.excepthook`` that captures unhandled exceptions.

    When installed, every unhandled exception reported to the interpreter is
    forwarded to the configured :class:`ErrorTrackerProtocol` and logged as a
    structured ``unhandled_exception`` event carrying the active correlation id
    (``trace_id``/``request_id`` bound via ``structlog.contextvars``), so the
    log line and the external error report share the same correlation id.

    Attributes:
        tracker: Error tracker notified for every unhandled exception.
        logger: Structured logger emitting the local log event.
    """

    def __init__(
        self,
        tracker: ErrorTrackerProtocol,
        logger: Any | None = None,
    ) -> None:
        """Initialize the hook.

        Args:
            tracker: Error tracker to notify on unhandled exceptions.
            logger: Structured logger; defaults to the module logger.
        """
        self._tracker = tracker
        self._logger = logger or get_logger(__name__)
        self._previous: Any = sys.__excepthook__

    def install(self) -> None:
        """Replace ``sys.excepthook``, chaining the previous hook."""
        self._previous = sys.excepthook
        sys.excepthook = self

    def uninstall(self) -> None:
        """Restore the previously installed hook, if still the active one."""
        if sys.excepthook is self:
            sys.excepthook = self._previous

    def __call__(
        self,
        exc_type: type[BaseException],
        exc: BaseException,
        tb: Any,
    ) -> None:
        """Capture the exception, log it with the correlation id, chain on.

        Args:
            exc_type: Type of the unhandled exception.
            exc: The unhandled exception instance.
            tb: Traceback object for the exception.
        """
        self._tracker.capture_exception(exc)
        event: dict[str, str] = {
            "error_type": exc_type.__name__,
            "error_message": str(exc) or repr(exc),
        }
        try:
            ctx = structlog.contextvars.get_contextvars()
        except (ImportError, AttributeError):
            ctx = {}
        corr = ctx.get("trace_id") or ctx.get("request_id")
        if corr is not None:
            event["correlation_id"] = str(corr)
            for key in ("trace_id", "request_id", "span_id"):
                if ctx.get(key) is not None:
                    event[key] = str(ctx[key])
        self._logger.error("unhandled_exception", **event)
        if self._previous is not None:
            self._previous(exc_type, exc, tb)


def install_unhandled_exception_hook(
    tracker: ErrorTrackerProtocol,
    logger: Any | None = None,
) -> UnhandledExceptionHook:
    """Install an unhandled-exception hook and return it for later uninstall.

    Args:
        tracker: Error tracker to notify for every unhandled exception.
        logger: Structured logger for the local log event.

    Returns:
        The installed hook; call ``hook.uninstall()`` to restore the
        previously active ``sys.excepthook``.

    Example:
        ```python
        from quadkit.monitor.error_tracking import (
            install_unhandled_exception_hook,
            setup_error_tracking,
        )

        hook = install_unhandled_exception_hook(
            setup_error_tracking(MonitorConfig().error_tracking)
        )
        # ... run the application ...
        hook.uninstall()
        ```
    """
    hook = UnhandledExceptionHook(tracker, logger)
    hook.install()
    return hook


__all__ = [
    "ErrorTrackerProtocol",
    "NullErrorTracker",
    "SentryErrorTracker",
    "UnhandledExceptionHook",
    "install_unhandled_exception_hook",
    "setup_error_tracking",
]
