"""Webhook domain exception hierarchy."""

from __future__ import annotations

from quadkit.contracts.exceptions.domain import DomainError


class WebhookError(DomainError):
    """Base exception for webhook domain operations."""

    _code = "QK_ERR_WEBHOOK_001"


__all__ = ["WebhookError"]
