"""Tests for MCP transport module."""

from __future__ import annotations

import pytest
from abc import ABC


class TestAbstractTransport:
    """Tests for AbstractTransport."""

    def test_import(self) -> None:
        from quadkit.ai.mcp.transport.base import AbstractTransport

        assert AbstractTransport is not None

    def test_is_abc(self) -> None:
        from quadkit.ai.mcp.transport.base import AbstractTransport

        assert issubclass(AbstractTransport, ABC)

    def test_has_start_method(self) -> None:
        from quadkit.ai.mcp.transport.base import AbstractTransport

        assert hasattr(AbstractTransport, "start")

    def test_has_stop_method(self) -> None:
        from quadkit.ai.mcp.transport.base import AbstractTransport

        assert hasattr(AbstractTransport, "stop")

    def test_has_send_method(self) -> None:
        from quadkit.ai.mcp.transport.base import AbstractTransport

        assert hasattr(AbstractTransport, "send")

    def test_has_receive_method(self) -> None:
        from quadkit.ai.mcp.transport.base import AbstractTransport

        assert hasattr(AbstractTransport, "receive")


class TestTransportExports:
    """Tests for transport module exports."""

    def test_all_exported(self) -> None:
        from quadkit.ai.mcp import transport

        expected = ["AbstractTransport"]
        for name in expected:
            assert hasattr(transport, name)