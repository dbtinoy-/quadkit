"""Structlog processors for the Quadkit logging pipeline.

Provides context injection, redaction, OpenTelemetry integration,
per-logger level filtering, and deterministic log sampling.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import threading
from typing import Any

import structlog

from quadkit.logging import get_logger
from quadkit.logging.redaction import get_redactor

logger = get_logger(__name__)
_otel_warned = [False]
from quadkit.logging.types import _LOGLEVEL_TO_INT, LogLevel

# ---------------------------------------------------------------------------
# Internal state — mutable at startup, set by configure_logging()
# ---------------------------------------------------------------------------


@dataclass
class _LoggingState:
    """Container for mutable runtime logging configuration.

    All fields are written once during ``configure_logging()`` before the
    application starts serving requests.  A lock protects against the rare
    case where ``configure_logging()`` is called concurrently (e.g. in
    tests or dynamic reconfiguration).
    """

    logger_levels: dict[str, int] = field(default_factory=dict)
    service_name: str = ""
    sampling_enabled: bool = False
    sampling_default_rate: float = 1.0
    sampling_rules: dict[str, float] = field(default_factory=dict)


_state = _LoggingState()
_state_lock = threading.Lock()

# Mapping from UPPER-CASE level name → stdlib integer level.
# Derived from LogLevel to keep the single source of truth in types.py.
LEVEL_NAME_TO_INT: dict[str, int] = {
    lvl.value.upper(): _LOGLEVEL_TO_INT[lvl] for lvl in LogLevel
}


def _context_processor(
    logger: Any,
    method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Inject context variables (trace_id, request_id) into the event dict."""
    try:
        import structlog.contextvars as _sv

        ctx_data = _sv.get_contextvars()
        if ctx_data:
            event_dict.update(ctx_data)
    except (ImportError, AttributeError):
        pass
    return event_dict


def _redact_processor(
    logger: Any,
    method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Redact sensitive information from the event dict."""
    return get_redactor().redact_dict(event_dict)


def _otel_processor(
    logger: Any,
    method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Inject OpenTelemetry trace and span IDs into the event dict."""
    try:
        # Dotted import: opentelemetry is a PEP-420 namespace package, so
        # ``from opentelemetry import trace`` does not type-check against its
        # stubs; PLR0402 prefers the from-form.
        import opentelemetry.trace as trace  # noqa: PLR0402

        span = trace.get_current_span()
        if span and span.get_span_context().is_valid:
            ctx = span.get_span_context()
            event_dict["trace_id"] = format(ctx.trace_id, "032x")
            event_dict["span_id"] = format(ctx.span_id, "016x")
    except ImportError:
        if not _otel_warned[0]:
            _otel_warned[0] = True
            # No kwargs here: this warning can be the first log call of the
            # process, firing before configure_logging() resolves structlog's
            # lazy proxy — kwargs crash against the raw PrintLogger default.
            logger.warning(
                "opentelemetry_not_installed; install opentelemetry-api for "
                "trace_id/span_id injection into log events"
            )
    return event_dict


class _NamespacedCallsiteAdder:
    """Run structlog's ``CallsiteParameterAdder`` in the ``_`` namespace.

    Two problems with using the adder directly:

    1. It writes ``filename``, ``lineno``, ``module`` and ``func_name`` —
       ordinary domain words.  ``logger.info("module_booted",
       module=self.name)`` is a natural call (this repo had 111 of them) and
       the adder silently overwrote every one with the emitting *source*
       file's module.  Framework metadata therefore lives under ``_``-
       prefixed keys, the convention ``_logger_name`` already follows, and
       the plain names belong to the caller.
    2. Left to itself the adder reports ``_NamedLogger.info`` in
       ``logging/factory.py`` as the callsite of every log line in the
       process, because that wrapper is the nearest non-structlog frame.
       ``additional_ignores`` skips the framework's own logging package so
       the real caller is reported.

    The inner adder is run against a scratch dict so it cannot clobber a
    caller field on its way past.
    """

    __slots__ = ("_inner",)

    #: Keys structlog's adder may consult on the stdlib-bridge path.
    _PASSTHROUGH = ("_record", "_from_structlog")

    def __init__(self, inner: Any) -> None:
        self._inner = inner

    def __call__(
        self,
        logger: Any,
        method_name: str,
        event_dict: dict[str, Any],
    ) -> dict[str, Any]:
        scratch: dict[str, Any] = {
            key: event_dict[key] for key in self._PASSTHROUGH if key in event_dict
        }
        for key, value in self._inner(logger, method_name, scratch).items():
            if key in self._PASSTHROUGH:
                continue
            event_dict.setdefault(f"_{key}", value)
        return event_dict


def _add_logger_name(
    logger: Any,
    method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Safe replacement for structlog.stdlib.add_logger_name.

    Handles loggers that don't have a ``.name`` attribute (like
    ``PrintLogger``).  Writes ``_logger_name`` — the key ``get_logger()``
    already binds, and the framework namespace — not ``logger``, which a
    caller may legitimately want as a field of their own.
    """
    if "_logger_name" not in event_dict:
        name = getattr(logger, "name", None)
        if name:
            event_dict["_logger_name"] = name
    return event_dict


def _service_processor(
    logger: Any,
    method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Inject the configured service name into the event dict.

    Uses ``setdefault`` so an explicit ``service=`` supplied by the caller
    or via ``bind(service=...)`` wins over the configured default.
    """
    with _state_lock:
        service_name = _state.service_name
    if service_name and "service" not in event_dict:
        event_dict["service"] = service_name
    return event_dict


def _level_filter_processor(
    logger: Any,
    method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Filter log events based on per-logger level overrides.

    If the logger has a per-logger level configured via
    ``LoggingConfig.levels``, events below that level are dropped.
    This runs *after* the global level filter built into structlog's
    ``make_filtering_bound_logger`` so it can only *raise* the
    effective level for specific loggers, not lower it below global.

    Uses ``structlog.DropEvent`` to suppress filtered events.
    """
    with _state_lock:
        logger_levels = dict(_state.logger_levels)
    if not logger_levels:
        return event_dict

    logger_name: str = event_dict.get("logger", "") or getattr(logger, "name", "") or ""

    # Walk all prefixes, keeping the longest (most-specific) match.
    best_level: int | None = None
    best_len = 0
    for prefix, level_int in logger_levels.items():
        if logger_name == prefix or logger_name.startswith(prefix + "."):
            if len(prefix) > best_len:
                best_level = level_int
                best_len = len(prefix)

    if best_level is None:
        return event_dict

    # Map method_name to numeric level
    event_level = LEVEL_NAME_TO_INT.get(method_name.upper(), 0)
    if event_level < best_level:
        raise structlog.DropEvent

    return event_dict


def _sampling_processor(
    logger: Any,
    method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Deterministically sample log events to reduce volume.

    Uses a hash-based approach on the event key so that the same event
    is consistently included or excluded across process restarts.

    Events at WARNING or above are never sampled (always emitted).

    When an event is sampled out, raises ``structlog.DropEvent``.
    """
    with _state_lock:
        sampling_enabled = _state.sampling_enabled
        sampling_default_rate = _state.sampling_default_rate
        sampling_rules = dict(_state.sampling_rules)
    if not sampling_enabled:
        return event_dict

    # Never sample WARNING+ events — they are always important
    event_level = LEVEL_NAME_TO_INT.get(method_name.upper(), 0)
    if event_level >= LEVEL_NAME_TO_INT["WARNING"]:
        return event_dict

    event_key = str(event_dict.get("event", ""))
    rate = sampling_rules.get(event_key, sampling_default_rate)

    # rate >= 1.0 means log everything (no sampling)
    if rate >= 1.0:
        return event_dict
    # rate <= 0.0 means drop everything
    if rate <= 0.0:
        raise structlog.DropEvent

    # Deterministic: hash the event key and check against the rate
    digest = hashlib.md5(event_key.encode(), usedforsecurity=False).hexdigest()
    hash_fraction = int(digest[:8], 16) / 0xFFFFFFFF
    if hash_fraction > rate:
        raise structlog.DropEvent

    return event_dict


__all__ = [
    "LEVEL_NAME_TO_INT",
    "_LoggingState",
    "_NamespacedCallsiteAdder",
    "_add_logger_name",
    "_context_processor",
    "_level_filter_processor",
    "_otel_processor",
    "_redact_processor",
    "_sampling_processor",
    "_service_processor",
    "_state",
    "_state_lock",
]
