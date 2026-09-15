"""Logger creation and retrieval for the Quadkit Framework.

Provides ``get_logger()`` for obtaining structlog bound-loggers with a
``.name`` attribute, and ``LoggerFactoryImpl`` which implements the
``LoggerFactoryProtocol`` protocol.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

import structlog

if TYPE_CHECKING:
    from quadkit.contracts.core.logging import LoggerProtocol


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

    def debug(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._inner.debug(msg, *args, **kwargs)

    def info(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._inner.info(msg, *args, **kwargs)

    def warning(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._inner.warning(msg, *args, **kwargs)

    def error(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._inner.error(msg, *args, **kwargs)

    def critical(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._inner.critical(msg, *args, **kwargs)

    def exception(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._inner.exception(msg, *args, **kwargs)

    def bind(self, **kwargs: Any) -> _NamedLogger:
        result = self._inner.bind(**kwargs)
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

    def __init__(self, config: Any | None = None) -> None:
        self._config = config

    def get_logger(self, name: str | None = None) -> LoggerProtocol:
        """Get or create a logger, optionally binding the service name."""
        logger = get_logger(name)
        if name:
            try:
                return cast("LoggerProtocol", logger.bind(service=name))
            except (AttributeError, TypeError):
                return cast("LoggerProtocol", logger)
        return cast("LoggerProtocol", logger)


__all__ = [
    "LoggerFactoryImpl",
    "_NamedLogger",
    "get_logger",
]
