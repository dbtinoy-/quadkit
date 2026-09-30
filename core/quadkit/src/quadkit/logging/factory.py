"""Logger creation and retrieval for the Quadkit Framework.

Provides ``get_logger()`` for obtaining structlog bound-loggers with a
``.name`` attribute, and ``LoggerFactoryImpl`` which implements the
``LoggerFactoryProtocol`` protocol.

A logging call must never raise.  structlog names the message parameter
``event``, so ``logger.info("task_finished", event=evt.name)`` is a
``TypeError`` — raised from inside the ``except`` block that was trying to
report a failure.  ``_deconflict()`` moves such a field to ``event_field``
instead of letting the diagnostic take down the path it was diagnosing;
``dev/checks/reserved_log_fields.py`` fails the build on the call site so
the remap stays a safety net rather than an interface.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

import structlog

if TYPE_CHECKING:
    from quadkit.contracts.core.logging import LoggerProtocol
    from quadkit.logging.config.models import LoggingConfig


def _deconflict(kwargs: dict[str, Any]) -> dict[str, Any]:
    """Move a caller field named ``event`` out of structlog's way.

    ``event`` is structlog's parameter for the log message, so passing it as
    a field raises ``TypeError``.  The field is preserved under
    ``event_field`` (``event_field_``, ``event_field__``, … if the caller
    already used that name) rather than dropped: a log call is a diagnostic
    and must not raise.
    """
    if "event" not in kwargs:
        return kwargs
    safe = dict(kwargs)
    key = "event_field"
    while key in safe:
        key += "_"
    safe[key] = safe.pop("event")
    return safe


class _NamedLogger:
    """Thin wrapper that adds ``.name`` to a structlog bound logger.

    Explicitly implements all ``LoggerProtocol`` members so the DI protocol
    validator can confirm compliance via ``hasattr`` at the class level.
    Delegation to the underlying structlog logger is handled by ``__getattr__``.
    """

    __slots__ = ("_inner", "name")

    def __init__(self, inner: Any, logger_name: str) -> None:
        object.__setattr__(self, "_inner", inner)
        object.__setattr__(self, "name", logger_name)

    # ── LoggerProtocol members ─────────────────────────────────────────────
    # These exist so ``hasattr(_NamedLogger, 'debug')`` etc. return True for
    # the DI validator.  At runtime the call is forwarded via __getattr__.

    # ``msg`` is positional-only: without the ``/`` this wrapper would add a
    # reserved word of its own making, and ``logger.info("x", msg=body)``
    # would fail with "got multiple values for argument 'msg'" even though
    # the underlying structlog logger has no such parameter.

    def debug(self, msg: str, /, *args: Any, **kwargs: Any) -> None:
        self._inner.debug(msg, *args, **_deconflict(kwargs))

    def info(self, msg: str, /, *args: Any, **kwargs: Any) -> None:
        self._inner.info(msg, *args, **_deconflict(kwargs))

    def warning(self, msg: str, /, *args: Any, **kwargs: Any) -> None:
        self._inner.warning(msg, *args, **_deconflict(kwargs))

    def error(self, msg: str, /, *args: Any, **kwargs: Any) -> None:
        self._inner.error(msg, *args, **_deconflict(kwargs))

    def critical(self, msg: str, /, *args: Any, **kwargs: Any) -> None:
        self._inner.critical(msg, *args, **_deconflict(kwargs))

    def exception(self, msg: str, /, *args: Any, **kwargs: Any) -> None:
        self._inner.exception(msg, *args, **_deconflict(kwargs))

    def bind(self, **kwargs: Any) -> _NamedLogger:
        result = self._inner.bind(**_deconflict(kwargs))
        return self if result is self._inner else _NamedLogger(result, self.name)

    def unbind(self, *keys: str) -> _NamedLogger:
        result = self._inner.unbind(*keys)
        return self if result is self._inner else _NamedLogger(result, self.name)

    # ── Dynamic attribute delegation ───────────────────────────────────────

    def __getattr__(self, item: str) -> Any:
        attr = getattr(self._inner, item)
        # Wrap chaining methods so they return a _NamedLogger
        if item in ("new", "clone") and callable(attr):

            def _wrapped(*args: Any, **kwargs: Any) -> Any:
                result = attr(*args, **kwargs)
                if result is self._inner:
                    return self
                return _NamedLogger(result, self.name)

            return _wrapped
        return attr

    def __dir__(self) -> list[str]:
        return list({*dir(self._inner), "name"})


def get_logger(name: str | None = None) -> Any:
    """Get a structlog logger instance.

    Args:
        name: Logger name.  If ``None``, returns the root ``"quadkit"``
            logger. If the name does not start with ``"quadkit."``, that
            prefix is prepended automatically.

    Returns:
        A structlog bound logger with a ``.name`` attribute.
    """
    if name is None:
        logger_name = "quadkit"
    elif name.startswith("quadkit."):
        logger_name = name
    else:
        logger_name = f"quadkit.{name}"

    # Pass _logger_name as initial_values so the lazy proxy is NOT resolved
    # at import time.  Calling .bind() here would eagerly resolve the proxy
    # (BoundLoggerLazyProxy.bind() instantiates the wrapper class), fixing
    # the filtering wrapper at whatever _CONFIG is current — typically the
    # default BoundLoggerFilteringAtNotset before apply_config() runs.
    # By deferring resolution until the first log call, the wrapper respects
    # whichever level configure_logging() / apply_config() sets later.
    return _NamedLogger(
        structlog.get_logger(logger_name, _logger_name=logger_name),
        logger_name,
    )


class LoggerFactoryImpl:
    """Standard implementation of LoggerFactoryProtocol protocol.

    Args:
        config: Optional LoggingConfig for configuring loggers.
    """

    def __init__(self, config: LoggingConfig | None = None) -> None:
        self._config = config

    def get_logger(self, name: str | None = None) -> LoggerProtocol:
        """Get or create a logger.

        This used to ``bind(service=name)``.  ``service`` is the envelope
        field identifying the *application* (set by ``configure_logging()``
        and used for log routing), and ``_service_processor`` yields to a
        bound value — so every DI-resolved logger relabelled the service as
        whichever component had asked for it.  The logger name already
        travels in ``_logger_name``.
        """
        return cast("LoggerProtocol", get_logger(name))


__all__ = [
    "LoggerFactoryImpl",
    "_NamedLogger",
    "_deconflict",
    "get_logger",
]
