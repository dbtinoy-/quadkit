"""Audit verifier scheduler protocol (audit types moved to contracts/audit/)."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from quadkit.contracts.audit.types import AuditEntry

__all__ = ["AuditEntry", "AuditVerifierSchedulerProtocol"]


@runtime_checkable
class AuditVerifierSchedulerProtocol(Protocol):
    """Protocol for registering and scheduling the audit verifier task.

    Implementations are provided by the ``quadkit-sql`` package and registered
    in the DI container. Extension packages (e.g. ``the optional provider``) resolve
    this protocol from the container rather than importing concrete DB types.
    """

    def register_handler(self, task_provider: Any) -> None:
        """Register the audit verifier handler with a task provider.

        Args:
            task_provider: A task provider that accepts ``register_handler``.
        """
        ...

    def schedule(
        self,
        task_provider: Any,
        *,
        audit_table: str = "audit_log",
        key: bytes | None = None,
    ) -> str | None:
        """Schedule the periodic audit verifier job.

        Args:
            task_provider: A task provider/scheduler with ``schedule_job``.
            audit_table: Name of the audit table to verify.
            key: HMAC key used for checksum verification.

        Returns:
            Job ID returned by the scheduler, or ``None``.
        """
        ...
