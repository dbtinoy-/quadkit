"""AuditEntry value object and AuditOutcome enum for admin audit logging."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class AuditOutcome(str, Enum):
    """Categorised outcome of an admin audit event."""

    SUCCESS = "success"
    DENIED = "denied"
    ERRORED = "errored"


@dataclass(frozen=True)
class AuditEntry:
    """Immutable audit entry representing a single admin audit event.

    Captures who did what, to which resource, the outcome, request
    context metadata, and optional before/after state snapshots.

    Args:
        admin_user_id: Identifier of the admin user performing the action.
        action: Action name (e.g. 'delete_user', 'update_role').
        resource_type: Type of resource being acted upon.
        resource_id: Identifier of the specific resource instance.
        outcome: Categorised outcome — success, denied, or errored.
        before: Snapshot of resource state before the action.
        after: Snapshot of resource state after the action.
        correlation_id: Request correlation ID for tracing.
        request_id: Original request identifier.
        request_ip: Client IP address.
        metadata: Arbitrary supplementary metadata.
    """

    admin_user_id: str
    action: str
    resource_type: str
    resource_id: str | None
    outcome: AuditOutcome | str
    before: dict[str, Any] = field(default_factory=dict)
    after: dict[str, Any] = field(default_factory=dict)
    correlation_id: str | None = None
    request_id: str | None = None
    request_ip: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


__all__ = [
    "AuditEntry",
    "AuditOutcome",
]
