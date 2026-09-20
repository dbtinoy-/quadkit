"""P2 hook surface import verification for quadkit-web."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, is_dataclass

import pytest


def test_web_hooks_root_module_exists() -> None:
    import quadkit.web
    from quadkit.web.hooks import (
        WebRequestReceivedHook,
        WebResponsePreparedHook,
        WebServerStartedHook,
        WebServerStoppedHook,
    )

    assert WebRequestReceivedHook.__name__ == "WebRequestReceivedHook"
    assert WebResponsePreparedHook.__name__ == "WebResponsePreparedHook"
    assert WebServerStartedHook.__name__ == "WebServerStartedHook"
    assert WebServerStoppedHook.__name__ == "WebServerStoppedHook"
    assert quadkit.web.WebRequestReceivedHook is WebRequestReceivedHook
    assert quadkit.web.WebResponsePreparedHook is WebResponsePreparedHook
    assert quadkit.web.WebServerStartedHook is WebServerStartedHook
    assert quadkit.web.WebServerStoppedHook is WebServerStoppedHook


def test_web_hook_payloads_are_frozen_and_keyword_only() -> None:
    from quadkit.web.hooks import WebRequestReceivedHook, WebServerStartedHook

    request_hook = WebRequestReceivedHook(path="/health", method="GET")
    started_hook = WebServerStartedHook()

    assert is_dataclass(request_hook)
    assert is_dataclass(started_hook)

    with pytest.raises(TypeError):
        WebRequestReceivedHook("/health", "GET")

    with pytest.raises(FrozenInstanceError):
        request_hook.path = "/ready"
