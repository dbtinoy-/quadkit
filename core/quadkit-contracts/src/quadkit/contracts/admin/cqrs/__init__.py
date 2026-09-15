"""CQRS marker protocols for the admin system."""

from __future__ import annotations

from quadkit.contracts.admin.cqrs.command import AdminCommand
from quadkit.contracts.admin.cqrs.query import AdminQuery

__all__ = ["AdminCommand", "AdminQuery"]
