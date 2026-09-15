"""Tests for boot-time configuration validation in Application.start().

``QuadkitConfig.validate_for_environment()`` (e.g. blocking
``debug=True`` in production) must actually run during boot — before any
provider starts — and a violated ``error``-severity constraint must
abort startup with a ``ConfigurationError``.
"""

from __future__ import annotations

import pytest

from quadkit.app.base import Application, AppState
from quadkit.config import QuadkitConfig
from quadkit.contracts.core.config import Environment
from quadkit.contracts.exceptions.config import ConfigurationError


class TestBootTimeConfigValidation:
    """start() must refuse to boot on invalid configuration."""

    async def test_debug_in_production_refuses_to_start(self):
        app = Application(
            config=QuadkitConfig(debug=True, env=Environment.PRODUCTION)
        )
        with pytest.raises(ConfigurationError) as excinfo:
            await app.start()
        assert app.state == AppState.STOPPED
        err = excinfo.value
        assert "refusing to start" in str(err)
        assert "debug" in str(err)
        # The raised error must carry the structured ConfigIssue list.
        assert err.issues, "ConfigurationError must carry the ConfigIssue list"
        assert any(i.field == "debug" for i in err.issues)

    async def test_valid_production_config_starts(self):
        app = Application(
            config=QuadkitConfig(debug=False, env=Environment.PRODUCTION)
        )
        await app.start()
        assert app.state == AppState.RUNNING
        await app.stop()
        assert app.state == AppState.STOPPED

    async def test_debug_in_development_is_allowed(self):
        app = Application(
            config=QuadkitConfig(debug=True, env=Environment.DEVELOPMENT)
        )
        await app.start()
        assert app.state == AppState.RUNNING
        await app.stop()
