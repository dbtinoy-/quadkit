"""Projection tier enumeration for alert routing."""

from __future__ import annotations

from enum import Enum


class ProjectionTier(str, Enum):
    """Alert routing tier for a projection or SLO.

    Attributes:
        P0_PAGE: Page on-call immediately (PagerDuty, etc.).
        P1_BUSINESS_HOURS: Route to Slack during business hours;
            queue outside business hours.
        P2_DIGEST: Accumulate in a buffer and flush as a weekly digest.
    """

    P0_PAGE = "p0_page"
    P1_BUSINESS_HOURS = "p1_business_hours"
    P2_DIGEST = "p2_digest"


__all__ = ["ProjectionTier"]
