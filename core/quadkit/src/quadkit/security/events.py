"""Domain events for quadkit core security.

Emitted when security events occur (threats, secret rotation, guard denials).
Consumed by audit, monitoring, and security review systems.

Note: ``CsrfViolationEvent`` is defined here for completeness but CSRF
is HTTP-specific; that event is most useful from ``quadkit-web``.
"""

from __future__ import annotations

from dataclasses import dataclass

from quadkit.contracts.domain.events import DomainEvent

__all__ = [
    "CsrfViolationEvent",
    "SecretRotatedEvent",
    "SecurityGuardDeniedEvent",
    "ThreatDetectedEvent",
]


@dataclass(frozen=True, init=False)
class ThreatDetectedEvent(DomainEvent):
    """Emitted when a security threat is detected.

    Consumed by: security monitoring, audit, threat response systems.
    """

    threat_type: str = ""
    source_ip: str = ""
    resource: str = ""


@dataclass(frozen=True, init=False)
class SecretRotatedEvent(DomainEvent):
    """Emitted when a secret is rotated.

    Consumed by: audit, compliance, secret management systems.
    """

    secret_name: str = ""
    rotated_by: str = ""


@dataclass(frozen=True, init=False)
class CsrfViolationEvent(DomainEvent):
    """Emitted when a CSRF violation is detected.

    Consumed by: security monitoring, audit, threat response systems.
    """

    path: str = ""
    method: str = ""
    source_ip: str = ""


@dataclass(frozen=True, init=False)
class SecurityGuardDeniedEvent(DomainEvent):
    """Emitted when a security guard denies a request.

    Consumed by: audit, monitoring, access control analysis.
    """

    guard_name: str = ""
    resource: str = ""
    reason: str = ""
