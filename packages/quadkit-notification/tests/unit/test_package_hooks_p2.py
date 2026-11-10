"""P2 hook surface import verification for quadkit-notification."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, is_dataclass

import pytest


def test_notification_hooks_root_module_exists() -> None:
    import quadkit.notification
    from quadkit.notification.hooks import (
        NotificationFailedHook,
        NotificationSentHook,
    )

    assert NotificationSentHook.__name__ == "NotificationSentHook"
    assert NotificationFailedHook.__name__ == "NotificationFailedHook"
    assert quadkit.notification.NotificationSentHook is NotificationSentHook
    assert quadkit.notification.NotificationFailedHook is NotificationFailedHook


def test_notification_hook_payloads_are_frozen_and_keyword_only() -> None:
    from quadkit.notification.hooks import NotificationSentHook

    hook = NotificationSentHook(channel="sms", recipient_id="u1")

    assert is_dataclass(hook)

    with pytest.raises(TypeError):
        NotificationSentHook("sms", "u1")  # type: ignore[misc]

    with pytest.raises(FrozenInstanceError):
        hook.channel = "email"  # type: ignore[misc]
