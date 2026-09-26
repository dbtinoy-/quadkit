"""Periodic scheduled-worker base for quadkit.monitor.

Implements the shared scheduled-worker pattern against the contracts
:class:`~quadkit.contracts.infra.tasks.TaskManagerProtocol` so monitor
never imports ``quadkit.tasks`` directly.
"""

from __future__ import annotations

from quadkit.monitor.scheduling.scheduled_worker import MonitorScheduledWorker

__all__ = ["MonitorScheduledWorker"]
