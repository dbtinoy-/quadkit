"""Auth activity tracker — bounded, thread-safe, real counts."""

from __future__ import annotations

from quadkit.auth.services.activity_tracker import AuthActivityTracker


def test_failed_login_summary_counts_and_unique_ips() -> None:
    tracker = AuthActivityTracker()
    tracker.record_failed_login("10.0.0.1")
    tracker.record_failed_login("10.0.0.1")
    tracker.record_failed_login("10.0.0.2")
    count, unique_ips = tracker.failed_login_summary(window_minutes=60)
    assert count == 3
    assert unique_ips == 2


def test_refresh_summary_rate_and_total() -> None:
    tracker = AuthActivityTracker()
    for _ in range(60):
        tracker.record_refresh()
    rate, total = tracker.refresh_summary(window_minutes=60)
    assert total == 60
    assert rate == 1.0


def test_window_expiry_drops_old_events() -> None:
    now_holder = {"t": 0.0}
    tracker = AuthActivityTracker(now=lambda: now_holder["t"])
    tracker.record_failed_login("10.0.0.1")
    now_holder["t"] += 61 * 60  # 61 minutes later
    count, _ = tracker.failed_login_summary(window_minutes=60)
    assert count == 0


def test_failed_login_defaults_to_unknown_ip() -> None:
    tracker = AuthActivityTracker()
    tracker.record_failed_login()
    count, unique_ips = tracker.failed_login_summary(window_minutes=60)
    assert count == 1
    assert unique_ips == 1


__all__ = [
    "test_failed_login_defaults_to_unknown_ip",
    "test_failed_login_summary_counts_and_unique_ips",
    "test_refresh_summary_rate_and_total",
    "test_window_expiry_drops_old_events",
]
