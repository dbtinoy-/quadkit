"""P2 hook surface import verification for quadkit-storage."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, is_dataclass

import pytest


def test_storage_hooks_root_module_exists() -> None:
    import quadkit.storage
    from quadkit.storage.hooks import (
        ObjectDeletedHook,
        ObjectStoredHook,
    )

    assert ObjectStoredHook.__name__ == "ObjectStoredHook"
    assert ObjectDeletedHook.__name__ == "ObjectDeletedHook"
    assert quadkit.storage.ObjectStoredHook is ObjectStoredHook
    assert quadkit.storage.ObjectDeletedHook is ObjectDeletedHook


def test_storage_hook_payloads_are_frozen_and_keyword_only() -> None:
    from quadkit.storage.hooks import ObjectStoredHook

    hook = ObjectStoredHook(bucket="media", key="uploads/avatar.png")

    assert is_dataclass(hook)

    with pytest.raises(TypeError):
        ObjectStoredHook("media", "uploads/avatar.png")  # type: ignore[misc]

    with pytest.raises(FrozenInstanceError):
        hook.bucket = "other"  # type: ignore[misc]
