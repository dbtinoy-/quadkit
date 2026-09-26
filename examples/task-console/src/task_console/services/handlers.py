"""Convention followed: **Application service** — plain functions registered
through the real ``TaskProviderProtocol.register_handler()`` and
``register_scheduled_task()`` calls; nothing here fakes execution.

Job handlers for the Task Console demo.

Every handler is a plain callable — ``quadkit-tasks`` decides how it is
invoked (worker pool, middleware, DLQ routing, result storage). One handler
(``flaky_report``) deterministically fails on its first two attempts so the
console can show a real retry-then-succeed job, and one (``always_fails``)
never succeeds so the DLQ panel always has something real to inspect.
"""

from __future__ import annotations

import asyncio
import random

# Attempt counters keyed by a caller-supplied "attempt_key" kwarg so the
# console can trigger a fresh flaky run without restarting the process.
_flaky_attempts: dict[str, int] = {}


async def send_welcome_email(user_id: str, email: str) -> dict[str, object]:
    """Simulate delivering a welcome email; always succeeds quickly."""
    await asyncio.sleep(0.05)
    return {"user_id": user_id, "email": email, "delivered": True}


async def resize_image(
    image_id: str, width: int = 800, height: int = 600
) -> dict[str, object]:
    """Simulate an image-resize job with a small amount of "work"."""
    await asyncio.sleep(0.1)
    return {"image_id": image_id, "width": width, "height": height, "resized": True}


async def flaky_report(
    report_id: str, attempt_key: str | None = None
) -> dict[str, object]:
    """Fail on the first two attempts, then succeed — a real retry story.

    ``quadkit-tasks`` runs a job exactly once per dequeue unless a
    ``RetryPolicyProtocol`` is injected (this demo doesn't wire one), so a
    failure here routes straight to the real DLQ. Retrying it from the DLQ
    panel re-enqueues the *same* job, and this counter (keyed by
    ``attempt_key``, defaulting to ``report_id``) remembers how many times
    it has run — the third attempt finally succeeds.
    """
    key = attempt_key or report_id
    attempt = _flaky_attempts.get(key, 0) + 1
    _flaky_attempts[key] = attempt
    if attempt < 3:
        raise RuntimeError(f"transient report backend error (attempt {attempt}/3)")
    return {"report_id": report_id, "attempt": attempt, "generated": True}


async def always_fails(reason: str = "vendor timeout") -> dict[str, object]:
    """Deterministically fail so the DLQ panel always has a real entry."""
    raise RuntimeError(f"permanent failure: {reason}")


async def compute_digest(payload: str) -> dict[str, object]:
    """CPU-light "digest" job used by the scheduled cleanup demo."""
    await asyncio.sleep(0.02)
    return {"payload_len": len(payload), "checksum": sum(map(ord, payload)) % 997}


async def flaky_ping(jitter: bool = True) -> dict[str, object]:
    """Scheduled heartbeat job; occasionally slow to show duration variance."""
    if jitter:
        await asyncio.sleep(random.uniform(0.0, 0.05))
    return {"ping": "ok"}


def reset_flaky_attempts() -> None:
    """Test/demo helper: clear the in-process attempt counters."""
    _flaky_attempts.clear()


#: Registered against real handler names via ``TaskProviderProtocol.register_handler``.
HANDLERS: dict[str, object] = {
    "send_welcome_email": send_welcome_email,
    "resize_image": resize_image,
    "flaky_report": flaky_report,
    "always_fails": always_fails,
    "compute_digest": compute_digest,
    "flaky_ping": flaky_ping,
}

__all__ = ["HANDLERS", "reset_flaky_attempts"]
