"""D5: the admin panel uses its own HMAC CSRF layer.

The web CSRF middleware must not double-guard ``/admin`` routes — the admin
stack owns token handling there. This file pins that boundary: WebConfig's
default excluded paths include ``/admin``, and a user-supplied default
`WebConfig()` keeps it excluded.
"""

from __future__ import annotations

from quadkit.web.config import WebConfig


class TestAdminWebCsrfBoundary:
    """Web CSRF must hand /admin to the admin HMAC layer."""

    def test_default_web_config_excludes_admin_path(self) -> None:
        """WebConfig() defaults must keep /admin exempt from web CSRF."""
        web_cfg = WebConfig()
        assert "/admin" in web_cfg.security.csrf.excluded_paths

    def test_admin_paths_can_be_overridden(self) -> None:
        """Operators may narrow the admin exclusion if they disable admin auth."""
        from quadkit.web.security.config import CSRFConfig, SecurityConfig

        web_cfg = WebConfig(
            security=SecurityConfig(
                csrf=CSRFConfig(enabled=True, excluded_paths=["/health", "/metrics"]),
            ),
        )
        assert "/admin" not in web_cfg.security.csrf.excluded_paths
