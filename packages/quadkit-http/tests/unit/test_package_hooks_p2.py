"""P2 hook surface import verification for quadkit-http."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, is_dataclass

import pytest


def test_http_hooks_root_module_exists() -> None:
    import quadkit.http
    from quadkit.http.hooks import (
        HTTPRequestSentHook,
        HTTPResponseReceivedHook,
    )

    assert HTTPRequestSentHook.__name__ == "HTTPRequestSentHook"
    assert HTTPResponseReceivedHook.__name__ == "HTTPResponseReceivedHook"
    assert quadkit.http.HTTPRequestSentHook is HTTPRequestSentHook
    assert quadkit.http.HTTPResponseReceivedHook is HTTPResponseReceivedHook


def test_http_hook_payloads_are_frozen_and_keyword_only() -> None:
    from quadkit.http.hooks import HTTPRequestSentHook, HTTPResponseReceivedHook

    sent = HTTPRequestSentHook(method="GET", url="https://api.example.com/health")
    received = HTTPResponseReceivedHook(
        method="GET", url="https://api.example.com/health", status_code=200
    )

    assert is_dataclass(sent)
    assert is_dataclass(received)

    with pytest.raises(TypeError):
        HTTPRequestSentHook("GET", "https://api.example.com")  # type: ignore[misc]

    with pytest.raises(FrozenInstanceError):
        sent.method = "POST"  # type: ignore[misc]
