"""Structured, context-aware logging for Quadkit Framework.

Fully structlog-based logging pipeline with no stdlib logging dependencies.
Configuration driven by ``LoggingConfig`` and applied via ``configure_logging``.

Exports:
    get_logger: Factory for obtaining a structured logger bound to a module.
    configure_logging: Apply ``LoggingConfig`` to the active pipeline.
    apply_config: Low-level configuration application.
    LoggerFactoryProtocol, LoggerFactoryImpl: Factory classes for logger creation.
    LoggerProtocol: Protocol for structured loggers.
    RedactorProtocol: Protocol for sensitive-data redaction.
    Logger: Alias for ``LoggerProtocol``.
    QueryLogEntry, QueryLoggerProtocol: Database query log contracts.
    CRITICAL, DEBUG, ERROR, INFO, WARNING: Log-level name constants.
"""

from __future__ import annotations

__path__ = __import__("pkgutil").extend_path(__path__, __name__)

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from quadkit.contracts.core.logging import (
        LoggerFactoryProtocol,
        LoggerProtocol,
        RedactorProtocol,
    )
    from quadkit.contracts.data.sql.query_log import QueryLogEntry, QueryLoggerProtocol
    from quadkit.logging.config.models import LoggingConfig as LoggingConfig
    from quadkit.logging.configurator import (
        apply_config,
        configure_logging,
        reset_logging,
    )
    from quadkit.logging.constants import CRITICAL, DEBUG, ERROR, INFO, WARNING
    from quadkit.logging.factory import (
        LoggerFactoryImpl,
        get_logger,
    )
    from quadkit.logging.types import LogLevel as LogLevel

_LAZY_IMPORTS: dict[str, str] = {
    # contracts
    "LoggerProtocol": "quadkit.contracts.core.logging",
    "RedactorProtocol": "quadkit.contracts.core.logging",
    "QueryLogEntry": "quadkit.contracts.data.sql.query_log",
    "QueryLoggerProtocol": "quadkit.contracts.data.sql.query_log",
    # config
    "apply_config": "quadkit.logging.configurator",
    "configure_logging": "quadkit.logging.configurator",
    "reset_logging": "quadkit.logging.configurator",
    # factory
    "LoggerFactoryImpl": "quadkit.logging.factory",
    "LoggerFactoryProtocol": "quadkit.contracts.core.logging",
    "get_logger": "quadkit.logging.factory",
    # constants
    "CRITICAL": "quadkit.logging.constants",
    "DEBUG": "quadkit.logging.constants",
    "ERROR": "quadkit.logging.constants",
    "INFO": "quadkit.logging.constants",
    "WARNING": "quadkit.logging.constants",
    # types
    "LogLevel": "quadkit.logging.types",
    # config model
    "LoggingConfig": "quadkit.logging.config.models",
    # provider
    "LoggingProvider": "quadkit.logging.di.provider",
}

# Logger is a public alias for LoggerProtocol (same module, different attr name).
_ALIASED_IMPORTS: dict[str, tuple[str, str]] = {
    "Logger": ("quadkit.contracts.core.logging", "LoggerProtocol"),
}


def __getattr__(name: str) -> Any:
    if name in _LAZY_IMPORTS:
        import importlib

        module = importlib.import_module(_LAZY_IMPORTS[name])
        value = getattr(module, name)
        globals()[name] = value
        return value
    if name in _ALIASED_IMPORTS:
        import importlib

        module_path, attr = _ALIASED_IMPORTS[name]
        value = getattr(importlib.import_module(module_path), attr)
        globals()[name] = value
        return value
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)


def __dir__() -> list[str]:
    return list(_LAZY_IMPORTS.keys()) + list(_ALIASED_IMPORTS.keys())


__all__ = (
    "CRITICAL",
    "DEBUG",
    "ERROR",
    "INFO",
    "WARNING",
    "LogLevel",
    "Logger",
    "LoggerFactoryImpl",
    "LoggerFactoryProtocol",
    "LoggerProtocol",
    "LoggingConfig",
    "LoggingProvider",
    "QueryLogEntry",
    "QueryLoggerProtocol",
    "RedactorProtocol",
    "apply_config",
    "configure_logging",
    "get_logger",
    "reset_logging",
)
