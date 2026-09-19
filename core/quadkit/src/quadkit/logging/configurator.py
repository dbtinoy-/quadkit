"""Logging system configuration for the Quadkit Framework.

Provides ``configure_logging()`` and ``apply_config()`` which bootstrap
the structlog pipeline with context injection, redaction, sampling, and
per-logger level overrides.
"""

from __future__ import annotations

import logging as _stdlib_logging
from typing import Any

import structlog
from structlog.stdlib import ProcessorFormatter

# Re-export processor module-level state so ``configure_logging`` can
# mutate it.  The actual mutable dicts/bools live in ``processors.py``.
import quadkit.logging.processors as _proc
from quadkit.logging.processors import (
    LEVEL_NAME_TO_INT,
    _add_logger_name,
    _context_processor,
    _level_filter_processor,
    _otel_processor,
    _redact_processor,
    _sampling_processor,
    _service_processor,
)
from quadkit.logging.redaction import (
    _DEFAULT_FIELD_DENYLIST,
    DefaultRedactor,
    NoOpRedactor,
    set_redactor,
)


def configure_logging(
    level: str = "INFO",
    json_format: bool = False,
    service_name: str = "quadkit-app",
    levels: dict[str, str] | None = None,
    sampling_enabled: bool = False,
    sampling_default_rate: float = 1.0,
    sampling_rules: dict[str, float] | None = None,
    redaction_enabled: bool = True,
    redaction_field_denylist: tuple[str, ...] | None = None,
) -> None:
    """Bootstrap the logging system using pure structlog.

    Args:
        level: Global minimum log level (DEBUG, INFO, WARNING, ERROR,
            CRITICAL).
        json_format: If ``True``, render logs as JSON; otherwise use
            human-readable console output.
        service_name: Application name injected into log context.
        levels: Per-logger level overrides. Keys are logger name prefixes,
            values are level strings.  Example:
            ``{"quadkit.di": "DEBUG", "the optional provider module": "WARNING"}``.
        sampling_enabled: Enable deterministic log sampling.
        sampling_default_rate: Default sample rate (1.0 = log everything,
            0.1 = log ~10%).
        sampling_rules: Per-event sampling rates keyed by event name.
            Example: ``{"request_received": 0.01}``.
        redaction_enabled: Install a field redactor for log events.
            Defaults to True (safe by default).
        redaction_field_denylist: Field names masked in log events; when
            None, the default field denylist is used.
    """
    # Apply per-logger level overrides and sampling config — guarded by lock
    # so that concurrent calls to configure_logging() (e.g. in tests) are safe.
    with _proc._state_lock:
        _proc._state.logger_levels.clear()
        if levels:
            for name, lvl in levels.items():
                numeric = LEVEL_NAME_TO_INT.get(lvl.upper())
                if numeric is not None:
                    _proc._state.logger_levels[name] = numeric

        _proc._state.service_name = service_name
        _proc._state.sampling_enabled = sampling_enabled
        _proc._state.sampling_default_rate = sampling_default_rate
        _proc._state.sampling_rules.clear()
        _proc._state.sampling_rules.update(sampling_rules or {})

        if redaction_enabled:
            set_redactor(
                DefaultRedactor(
                    field_denylist=redaction_field_denylist or _DEFAULT_FIELD_DENYLIST
                )
            )
        else:
            set_redactor(NoOpRedactor())

    timestamper = structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S")

    shared_processors: list[Any] = [
        structlog.stdlib.add_log_level,
        _add_logger_name,
        timestamper,
        _context_processor,
        _service_processor,
        _otel_processor,
        _redact_processor,
        structlog.processors.CallsiteParameterAdder(
            {
                structlog.processors.CallsiteParameter.FILENAME,
                structlog.processors.CallsiteParameter.LINENO,
                structlog.processors.CallsiteParameter.MODULE,
                structlog.processors.CallsiteParameter.FUNC_NAME,
            },
        ),
        structlog.processors.StackInfoRenderer(),
    ]

    # Per-logger level filter (runs after global filter, can only raise level)
    if _proc._state.logger_levels:
        shared_processors.append(_level_filter_processor)

    # Sampling processor
    if _proc._state.sampling_enabled:
        shared_processors.append(_sampling_processor)

    if json_format:
        processors = [
            *shared_processors,
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]
    else:
        processors = [
            *shared_processors,
            structlog.processors.ExceptionPrettyPrinter(),
            structlog.dev.ConsoleRenderer(colors=True),
        ]

    structlog.configure(
        processors=processors,
        logger_factory=structlog.PrintLoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(
                structlog.stdlib.logging,
                level.upper(),
                structlog.stdlib.logging.INFO,
            ),
        ),
        cache_logger_on_first_use=True,
    )

    # Bridge stdlib logging into structlog's output pipeline so that
    # third-party libraries (SQLAlchemy, asyncpg, httpx, Granian) emit
    # through the same structured logger with consistent formatting.
    #
    # Note: foreign (stdlib) log records bypass the structlog processor
    # chain — redaction, sampling, context injection, and OTEL enrichment
    # all apply to structlog-native loggers only.  The foreign_pre_chain
    # below adds basic enrichment (level, timestamp) for console rendering.
    _stdlib_handler = _stdlib_logging.StreamHandler()
    _renderer = (
        structlog.processors.JSONRenderer()
        if json_format
        else structlog.dev.ConsoleRenderer()
    )
    _stdlib_handler.setFormatter(
        ProcessorFormatter(
            processor=_renderer,
            foreign_pre_chain=[
                structlog.stdlib.add_log_level,
                structlog.stdlib.ExtraAdder(),
                timestamper,
            ],
        )
    )

    # Remove any previously attached bridge handlers to avoid duplicates
    root = _stdlib_logging.getLogger()
    for h in list(root.handlers):
        if isinstance(h, _stdlib_logging.StreamHandler) and isinstance(
            getattr(h, "formatter", None), ProcessorFormatter
        ):
            root.removeHandler(h)
    root.addHandler(_stdlib_handler)
    _stdlib_logging.getLogger().setLevel(
        getattr(
            _stdlib_logging,
            level.upper(),
            _stdlib_logging.INFO,
        ),
    )


def apply_config(logging_config: Any, *, service_name: str | None = None) -> None:
    """Apply a LoggingConfig object to configure the logging system.

    Args:
        logging_config: A ``LoggingConfig`` (or compatible) instance
            providing ``level``, ``json_format``, ``levels``, and
            ``sampling`` attributes.
        service_name: Service name injected into log events as ``service``.
            When omitted, ``configure_logging``'s default is used.
    """
    level = getattr(logging_config, "level", "INFO")
    json_format = getattr(logging_config, "json_format", False)
    levels = getattr(logging_config, "levels", None)

    # Sampling config (nested DomainModel)
    sampling = getattr(logging_config, "sampling", None)
    sampling_enabled = False
    sampling_default_rate = 1.0
    sampling_rules: dict[str, float] = {}
    if sampling is not None:
        sampling_enabled = getattr(sampling, "enabled", False)
        sampling_default_rate = getattr(sampling, "default_rate", 1.0)
        sampling_rules = getattr(sampling, "rules", {})

    # Redaction config (nested DomainModel)
    redaction = getattr(logging_config, "redaction", None)
    redaction_enabled = True
    redaction_field_denylist: tuple[str, ...] | None = None
    if redaction is not None:
        redaction_enabled = getattr(redaction, "enabled", True)
        redaction_field_denylist = getattr(redaction, "field_denylist", None)

    configure_logging(
        level=level,
        json_format=json_format,
        service_name=service_name or "quadkit-app",
        levels=levels,
        sampling_enabled=sampling_enabled,
        sampling_default_rate=sampling_default_rate,
        sampling_rules=sampling_rules,
        redaction_enabled=redaction_enabled,
        redaction_field_denylist=redaction_field_denylist,
    )


def reset_logging() -> None:
    """Remove all handlers from the root logger (teardown).

    Intended for test cleanup and graceful shutdown. Removes all
    ``StreamHandler`` instances whose formatter is a ``ProcessorFormatter``
    (i.e. handlers attached by :func:`configure_logging`).
    """
    root = _stdlib_logging.getLogger()
    for h in list(root.handlers):
        if isinstance(h, _stdlib_logging.StreamHandler) and isinstance(
            getattr(h, "formatter", None), ProcessorFormatter
        ):
            root.removeHandler(h)


__all__ = [
    "apply_config",
    "configure_logging",
    "reset_logging",
]
