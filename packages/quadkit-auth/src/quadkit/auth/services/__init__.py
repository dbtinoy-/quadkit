"""Authentication services."""

from __future__ import annotations

from quadkit.auth.services.activity_tracker import AuthActivityTracker
from quadkit.auth.services.result_pattern_service import AuthServiceWithResultPattern

__all__ = ["AuthActivityTracker", "AuthServiceWithResultPattern"]
