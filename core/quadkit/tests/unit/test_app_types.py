"""Tests for app state types."""

import pytest

from quadkit.app.base import AppState


class TestAppState:
    """Tests for AppState enum."""

    def test_app_state_values(self) -> None:
        """Test AppState enum values."""
        assert AppState.CREATED.value == "created"
        assert AppState.STARTING.value == "starting"
        assert AppState.RUNNING.value == "running"
        assert AppState.STOPPING.value == "stopping"
        assert AppState.STOPPED.value == "stopped"

    def test_app_state_members(self) -> None:
        """Test AppState has expected members."""
        members = list(AppState)
        assert len(members) == 5

    def test_app_state_representation(self) -> None:
        """Test AppState string representation."""
        states = [
            AppState.CREATED,
            AppState.STARTING,
            AppState.RUNNING,
            AppState.STOPPING,
            AppState.STOPPED,
        ]
        values = [s.value for s in states]
        assert values == ["created", "starting", "running", "stopping", "stopped"]
