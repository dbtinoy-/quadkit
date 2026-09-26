"""Tier-aware alert routing dispatcher."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from quadkit.contracts.monitor.projection_tier import ProjectionTier
    from quadkit.contracts.observability.metrics import AlertDispatcherProtocol


__all__ = ["TierAwareAlertDispatcher"]


class TierAwareAlertDispatcher:
    """Routes alerts based on tier in ``context["tier"]``.

    Implements :class:`~quadkit.contracts.observability.metrics.AlertDispatcherProtocol`:
    delegates to per-tier inner dispatchers when a matching tier is found,
    otherwise falls through to the default dispatcher.

    Args:
        channels: Mapping of tier to its dedicated dispatcher.
        default_dispatcher: Fallback dispatcher for unconfigured tiers.
    """

    def __init__(
        self,
        channels: dict[ProjectionTier, AlertDispatcherProtocol],
        default_dispatcher: AlertDispatcherProtocol,
    ) -> None:
        self._channels = dict(channels)
        self._default = default_dispatcher

    def _resolve(self, context: dict[str, Any] | None) -> AlertDispatcherProtocol:
        """Pick the dispatcher for *context*, or the default."""
        tier_str = (context or {}).get("tier")
        if tier_str is not None:
            from quadkit.contracts.monitor.projection_tier import ProjectionTier

            try:
                tier = ProjectionTier(tier_str)
                if tier in self._channels:
                    return self._channels[tier]
            except ValueError:
                pass
        return self._default

    async def send_alert(
        self,
        title: str,
        message: str,
        severity: str,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Dispatch an alert to the tier-appropriate channel."""
        dispatcher = self._resolve(context)
        await dispatcher.send_alert(title, message, severity, context)

    async def send_metric_alert(
        self,
        metric_name: str,
        current_value: float,
        threshold: float,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Dispatch a metric alert to the tier-appropriate channel."""
        dispatcher = self._resolve(context)
        await dispatcher.send_metric_alert(
            metric_name, current_value, threshold, context
        )
