"""Redaction utilities for sensitive data in logs and error output."""

from __future__ import annotations

import contextvars
import re
from typing import Any

from quadkit.contracts.core.logging import RedactorProtocol

_DEFAULT_FIELD_DENYLIST: frozenset[str] = frozenset(
    {
        "password",
        "passwd",
        "secret",
        "token",
        "api_key",
        "apikey",
        "authorization",
        "auth",
        "session_id",
        "session_token",
        "access_token",
        "refresh_token",
        "private_key",
        "client_secret",
    }
)

_SECRET_TOKENS: frozenset[str] = frozenset(
    {
        "password",
        "passwd",
        "secret",
        "token",
        "api_key",
        "apikey",
        "authorization",
        "auth",
        "credential",
        "credentials",
        "private",
        "dsn",
    }
)

_KEY_TAIL_PREFIXES: frozenset[str] = frozenset(
    {
        "api",
        "server",
        "auth",
        "access",
        "secret",
        "signing",
        "vapid",
        "apns",
        "session",
        "client",
        "private",
        "encryption",
        "license",
    }
)

_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")


def _is_sensitive_key(key: str) -> bool:
    """True when *key* carries a secret-bearing token.

    Matching normalizes camelCase and ``-``/``_`` separators into segments,
    then flags a key when any segment equals a secret token (masking
    ``auth_token``, ``apiKey``, ``dsn``, ``vapid_private_key``, ...) or when
    the final segment is ``key`` preceded by an auth-flavored prefix
    (``server_key``, ``access_key``). Benign lookalikes such as ``monkey``,
    ``keyboard``, ``token_count`` stay untouched.
    """
    normalized = _CAMEL_BOUNDARY.sub("_", key).lower().replace("-", "_")
    segments = [seg for seg in normalized.split("_") if seg]
    if not segments:
        return False
    if not any(seg in _SECRET_TOKENS for seg in segments):
        # Trailing "key"/"secret"-style names without a token segment still
        # count when prefixed by an auth-flavored word (server_key).
        return (
            len(segments) > 1
            and segments[-1] == "key"
            and segments[0] in _KEY_TAIL_PREFIXES
        )
    # A secret token is present; require it to anchor the *end* of the key
    # (or be paired with a value-ish suffix) so metric-style names such as
    # ``token_count`` / ``prompt_tokens`` keep flowing to logs.
    tail_ok = segments[-1] in _SECRET_TOKENS or segments[-1] in {
        "key",
        "id",
        "hash",
        "signature",
    }
    return tail_ok or segments[-1] in _KEY_TAIL_PREFIXES


class NoOpRedactor:
    """Default redactor that passes data through unchanged.

    Replace with a real implementation via ``set_redactor()`` or
    a context-local override for sensitive environments.
    """

    def redact_dict(self, data: dict[str, Any]) -> dict[str, Any]:
        return data

    def redact_value(self, value: Any) -> Any:
        return value


class DelegatingRedactor:
    """Redactor bound to the currently active pipeline redactor.

    Useful as the container-registered ``RedactorProtocol`` so application
    code that injects a redactor observes the same policy that the logging
    pipeline applies (configured via :func:`configure_logging`), instead of
    a stale NoOp instance.
    """

    def redact_dict(self, data: dict[str, Any]) -> dict[str, Any]:
        return get_redactor().redact_dict(data)

    def redact_value(self, value: Any) -> Any:
        return get_redactor().redact_value(value)


class DefaultRedactor:
    """Redact log fields whose names match the default field denylist.

    Masking is key-based only (no free-text pattern matching):
    top-level and nested dict keys matching a denylisted field name,
    case-insensitively, are replaced with the ``"<redacted>"`` sentinel.
    Non-denylisted values pass through unchanged, including nested
    containers which are recursed.

    Args:
        field_denylist: Field names to mask, matched case-insensitively.
            Defaults to ``_DEFAULT_FIELD_DENYLIST``.
    """

    def __init__(
        self,
        field_denylist: frozenset[str] | tuple[str, ...] | None = None,
    ) -> None:
        self._custom_list = field_denylist is not None
        if field_denylist is None:
            field_denylist = _DEFAULT_FIELD_DENYLIST
        self._field_denylist = frozenset(f.lower() for f in field_denylist)

    def _matches(self, key: str) -> bool:
        """Case-insensitive sensitive-key match.

        With the default denylist, segment/camelCase token matching applies.
        An explicitly provided ``field_denylist`` replaces built-in matching
        entirely (historical contract): only its exact keys are masked.
        """
        if key.lower() in self._field_denylist:
            return True
        if field_denylist_was_explicit := getattr(self, "_custom_list", False):
            return False
        return _is_sensitive_key(key)

    def redact_dict(self, data: dict[str, Any]) -> dict[str, Any]:
        """Return ``data`` with denylisted keys masked, recursing containers.

        Args:
            data: The mapping to redact.

        Returns:
            A new mapping with matching keys set to ``"<redacted>"``.
        """
        return {
            key: ("<redacted>" if self._matches(key) else self.redact_value(value))
            for key, value in data.items()
        }

    def redact_value(self, value: Any) -> Any:
        """Redact a value, recursing nested dicts and lists.

        Args:
            value: The value to redact.

        Returns:
            The value with nested denylisted keys masked; non-container
            values pass through unchanged.
        """
        if isinstance(value, dict):
            return self.redact_dict(value)
        if isinstance(value, list):
            return [self.redact_value(item) for item in value]
        if isinstance(value, tuple):
            return tuple(self.redact_value(item) for item in value)
        return value


# ContextVar allows per-request redactor override (e.g., stricter
# redaction for certain tenants) while the container holds the default.
_redactor_var: contextvars.ContextVar[RedactorProtocol | None] = contextvars.ContextVar(
    "quadkit_redactor",
    default=None,
)


def get_redactor() -> RedactorProtocol:
    """Get the redactor active in the current context.

    Resolution order:
        1. Context-local override (set via ``set_redactor()``)
        2. No-op fallback (before :func:`configure_logging` has run)

    This is intentionally synchronous — redaction is called from
    structlog processors which are sync.  Install the process-wide policy
    with :func:`configure_logging` (or ``set_redactor``); if you want a
    container-managed redactor that follows the same policy, inject
    :class:`DelegatingRedactor`, not a directly-constructed ``NoOpRedactor``.
    """
    # 1. Context-local override (per-request or per-tenant)
    context_redactor = _redactor_var.get()
    if context_redactor is not None:
        return context_redactor

    # 2. Fallback to no-op until configure_logging() installs the policy
    return NoOpRedactor()


def set_redactor(
    redactor: RedactorProtocol,
) -> contextvars.Token[RedactorProtocol | None]:
    """Set a context-local redactor override.

    Returns a token for resetting via ``_redactor_var.reset(token)``.

    Usage::

        token = set_redactor(StrictRedactor())
        try:
            process_sensitive_request()
        finally:
            _redactor_var.reset(token)
    """
    return _redactor_var.set(redactor)


__all__ = [
    "DefaultRedactor",
    "DelegatingRedactor",
    "NoOpRedactor",
    "get_redactor",
    "set_redactor",
]
