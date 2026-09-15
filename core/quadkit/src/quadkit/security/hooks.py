"""Root hook payload surface for quadkit core security.

Defines canonical payload dataclasses for security guard/middleware hook points.
Actual hook registration and invocation use the framework's string-keyed
``HookRegistryProtocol`` action/filter APIs.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "SecurityGuardBlockedHook",
    "SecurityGuardPassedHook",
    "SecurityThreatDetectedHook",
]


@dataclass(frozen=True, kw_only=True)
class SecurityGuardPassedHook:
    """Payload fired when a security guard allows a request through.

    Attributes:
        guard_name: Name of the guard that passed the request.
    """

    guard_name: str


@dataclass(frozen=True, kw_only=True)
class SecurityGuardBlockedHook:
    """Payload fired when a security guard rejects a request.

    Attributes:
        guard_name: Name of the guard that blocked the request.
        reason: Short description of why the request was blocked.
    """

    guard_name: str
    reason: str


@dataclass(frozen=True, kw_only=True)
class SecurityThreatDetectedHook:
    """Payload fired when a security threat (e.g. injection attempt) is detected.

    Attributes:
        threat_type: Category of threat detected (e.g. ``"xss"``, ``"sqli"``).
        source: Origin of the suspicious input (e.g. field name or header).
    """

    threat_type: str
    source: str
