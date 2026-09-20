"""Tests for CSRFConfig defaults and CSRF middleware wiring in WebProvider."""

from __future__ import annotations

import pytest

from quadkit.web.security.config import CSRFConfig, SecurityConfig


class TestCsrfConfig:
    """Verify CSRFConfig field defaults and presence on SecurityConfig.

    CSRFConfig is the canonical class from quadkit.web.security.
    Web security defaults apply (enabled=False, samesite="Lax").
    Web-appropriate defaults (enabled=True, excluded_paths) are set in
    WebConfig.security's default_factory rather than on the class itself.
    """

    def test_csrf_config_defaults(self) -> None:
        """CSRFConfig has excluded_paths support and sensible defaults."""
        cfg = CSRFConfig()
        assert isinstance(cfg.excluded_paths, list)
        assert cfg.cookie_secure is True
        assert cfg.cookie_name == "csrf_token"
        assert cfg.header_name == "X-CSRF-Token"

    def test_webconfigcors_security_has_csrf_enabled_by_default(self) -> None:
        """WebConfig().security.csrf is enabled by default for web's secure-by-default UX."""
        from quadkit.web.config import WebConfig

        web_cfg = WebConfig()
        assert web_cfg.security.csrf.enabled is True
        assert len(web_cfg.security.csrf.excluded_paths) > 0

    def test_web_config_default_excluded_paths_cover_api(self) -> None:
        """F-W2: cookie-authenticated /api/* mutations must be CSRF-protected,
        so '/api/' is not exempt by default; '/admin' is handed to the admin
        HMAC layer (D5)."""
        from quadkit.web.config import WebConfig

        web_cfg = WebConfig()
        assert "/api/" not in web_cfg.security.csrf.excluded_paths
        assert "/health" in web_cfg.security.csrf.excluded_paths
        assert "/metrics" in web_cfg.security.csrf.excluded_paths
        assert "/admin" in web_cfg.security.csrf.excluded_paths

    def test_web_security_config_has_csrf_field(self) -> None:
        """SecurityConfig must expose a `csrf` attribute of type CSRFConfig."""
        sec = SecurityConfig()
        assert hasattr(sec, "csrf")
        assert isinstance(sec.csrf, CSRFConfig)

    def test_csrf_config_can_be_enabled(self) -> None:
        """CSRFConfig.enabled can be set to True."""
        cfg = CSRFConfig(enabled=True)
        assert cfg.enabled is True

    def test_csrf_config_samesite_configurable(self) -> None:
        """cookie_samesite can be overridden."""
        cfg = CSRFConfig(cookie_samesite="strict")
        assert cfg.cookie_samesite == "strict"

    def test_csrf_config_excluded_paths_configurable(self) -> None:
        """excluded_paths can be replaced with a custom list."""
        cfg = CSRFConfig(excluded_paths=["/public/"])
        assert cfg.excluded_paths == ["/public/"]

    def test_csrf_config_secret_key_is_public_field(self) -> None:
        """F-W3: secret_key is a public field (populatable via env var)."""
        cfg = CSRFConfig(secret_key="test-secret-32bytes-long!!")
        secret = cfg.secret_key
        assert (
            secret.get_secret_value()
            if hasattr(secret, "get_secret_value")
            else secret
        ) == "test-secret-32bytes-long!!"

    def test_csrf_config_default_secret_key_is_none(self) -> None:
        """secret_key defaults to None (production validation requires it)."""
        cfg = CSRFConfig()
        assert cfg.secret_key is None


class TestCsrfFlagSync:
    """D1: enable_csrf is authoritative for disabling CSRF."""

    def test_enable_csrf_false_disables_csrf(self) -> None:
        """An explicit enable_csrf=False overrides csrf.enabled."""
        sec = SecurityConfig(enable_csrf=False, csrf=CSRFConfig(enabled=True))
        assert sec.csrf.enabled is False

    def test_enable_csrf_default_keeps_configured_csrf(self) -> None:
        """With the default flag, an explicit csrf sub-config wins."""
        sec = SecurityConfig(csrf=CSRFConfig(enabled=True))
        assert sec.csrf.enabled is True
        sec_disabled = SecurityConfig(csrf=CSRFConfig(enabled=False))
        assert sec_disabled.csrf.enabled is False

    def test_standalone_csrf_config_default_stays_false(self) -> None:
        """CSRFConfig() standalone default remains False."""
        assert CSRFConfig().enabled is False


class TestCsrfMiddlewareWiring:
    """Integration: CSRFProtectionMiddleware is wired when csrf.enabled = True."""

    @pytest.mark.asyncio
    async def test_csrf_middleware_present_by_default(self, test_bed) -> None:
        """CSRFProtectionMiddleware IS added by default because csrf.enabled = True (secure-by-default)."""
        from unittest.mock import MagicMock

        from quadkit.web.di.provider import WebProvider
        from quadkit.web.security.csrf.middleware import CSRFProtectionMiddleware

        web = await test_bed.resolve(WebProvider)

        added_middleware: list[type] = []

        def capture_add_middleware(cls: type, **_kwargs: object) -> None:
            added_middleware.append(cls)

        fake_app = MagicMock()
        fake_app.add_middleware = capture_add_middleware
        fake_container = MagicMock()

        await web._setup_middleware(fake_app, fake_container)

        # csrf.enabled defaults to True (secure-by-default) → CSRFProtectionMiddleware MUST be added
        assert CSRFProtectionMiddleware in added_middleware


class TestSecurityMasterSwitchWiring:
    """Integration: SecurityConfig.enabled turns the security subsystem off."""

    @pytest.mark.asyncio
    async def test_security_disabled_skips_both_middlewares(self, test_bed) -> None:
        """SecurityConfig(enabled=False) skips CSRF and security headers."""
        from unittest.mock import MagicMock

        from quadkit.web.di.provider import WebProvider
        from quadkit.web.middleware.security import SecurityHeadersMiddleware
        from quadkit.web.security.csrf.middleware import CSRFProtectionMiddleware

        web = await test_bed.resolve(WebProvider)
        web.web_config.security = SecurityConfig(enabled=False)

        added_middleware: list[type] = []

        def capture_add_middleware(cls: type, **_kwargs: object) -> None:
            added_middleware.append(cls)

        fake_app = MagicMock()
        fake_app.add_middleware = capture_add_middleware
        fake_container = MagicMock()

        await web._setup_middleware(fake_app, fake_container)

        assert CSRFProtectionMiddleware not in added_middleware
        assert SecurityHeadersMiddleware not in added_middleware

    @pytest.mark.asyncio
    async def test_enable_csrf_false_disables_middleware_kwargs(self, test_bed) -> None:
        """enable_csrf=False leaves csrf.enabled untouched but gates wiring."""
        from unittest.mock import MagicMock

        from quadkit.web.di.provider import WebProvider

        web = await test_bed.resolve(WebProvider)
        web.web_config.security.enable_csrf = False
        assert web.web_config.security.csrf.enabled is True

        added_middleware: list[type] = []

        def capture_add_middleware(cls: type, **_kwargs: object) -> None:
            added_middleware.append(cls)

        fake_app = MagicMock()
        fake_app.add_middleware = capture_add_middleware
        fake_container = MagicMock()

        await web._setup_middleware(fake_app, fake_container)

        from quadkit.web.security.csrf.middleware import CSRFProtectionMiddleware

        assert CSRFProtectionMiddleware not in added_middleware


class TestCsrfMiddlewareWiringEnabled:
    """Integration: CSRFProtectionMiddleware is wired when csrf.enabled = True."""

    @pytest.mark.asyncio
    async def test_csrf_middleware_present_when_enabled(self, test_bed) -> None:
        """When csrf.enabled = True, CSRFProtectionMiddleware is added to the stack."""
        from unittest.mock import MagicMock

        from quadkit.web.di.provider import WebProvider
        from quadkit.web.security.config import CSRFConfig
        from quadkit.web.security.csrf.middleware import CSRFProtectionMiddleware

        web = await test_bed.resolve(WebProvider)

        # Patch the security config to enable CSRF
        web.web_config.security.csrf = CSRFConfig(
            enabled=True,
            cookie_samesite="strict",
            cookie_secure=False,
            excluded_paths=["/health"],
        )

        added_middleware: list[type] = []

        def capture_add_middleware(cls: type, **_kwargs: object) -> None:
            added_middleware.append(cls)

        fake_app = MagicMock()
        fake_app.add_middleware = capture_add_middleware
        fake_container = MagicMock()

        await web._setup_middleware(fake_app, fake_container)

        assert CSRFProtectionMiddleware in added_middleware

    @pytest.mark.asyncio
    async def test_csrf_middleware_not_added_when_enable_csrf_disabled(
        self, test_bed
    ) -> None:
        """The enable_csrf convenience flag must gate middleware wiring."""
        from unittest.mock import MagicMock

        from quadkit.web.di.provider import WebProvider
        from quadkit.web.security.csrf.middleware import CSRFProtectionMiddleware

        web = await test_bed.resolve(WebProvider)

        web.web_config.security.enable_csrf = False

        added_middleware: list[type] = []

        def capture_add_middleware(cls: type, **_kwargs: object) -> None:
            added_middleware.append(cls)

        fake_app = MagicMock()
        fake_app.add_middleware = capture_add_middleware
        fake_container = MagicMock()

        await web._setup_middleware(fake_app, fake_container)

        assert CSRFProtectionMiddleware not in added_middleware


class TestProductionCsrfDefaults:
    """Production security templates and validation must keep CSRF on."""

    _PROD_SECRET = "prod-secret-key-32-bytes-long!!"

    def test_create_production_config_enables_csrf(self) -> None:
        """create_production_config() must enable CSRF and HSTS (secure by default)."""
        from quadkit.web.middleware.security import create_production_config

        cfg = create_production_config()
        assert cfg.csrf.enabled is True
        assert cfg.hsts.enabled is True

    def test_web_config_production_defaults_keep_csrf_enabled(self) -> None:
        """WebConfig(env="production") keeps CSRF and HSTS enabled by default."""
        from quadkit.web.config import WebConfig

        web_cfg = WebConfig(
            env="production",
            security=SecurityConfig(
                csrf=CSRFConfig(enabled=True, secret_key=self._PROD_SECRET),
                allowed_hosts=["example.com"],
            ),
        )
        assert web_cfg.security.csrf.enabled is True
        assert web_cfg.security.hsts.enabled is True

    def test_web_config_production_rejects_csrf_disabled(self) -> None:
        """WebConfig blocks CSRF-disabled configs in production."""
        from quadkit.web.config import WebConfig

        with pytest.raises(ValueError, match="CSRF protection is disabled"):
            WebConfig(
                env="production",
                security=SecurityConfig(csrf=CSRFConfig(enabled=False)),
            )

    def test_web_config_production_requires_secret_key(self) -> None:
        """D2: production CSRF requires a secret_key — fail closed."""
        from quadkit.web.config import WebConfig

        with pytest.raises(ValueError, match="secret_key"):
            WebConfig(
                env="production",
                security=SecurityConfig(csrf=CSRFConfig(enabled=True)),
            )

    def test_web_config_production_requires_allowed_hosts(self) -> None:
        """D3: production host validation requires an allowed_hosts allowlist."""
        from quadkit.web.config import WebConfig

        with pytest.raises(ValueError, match="allowed_hosts"):
            WebConfig(
                env="production",
                security=SecurityConfig(
                    csrf=CSRFConfig(enabled=True, secret_key=self._PROD_SECRET),
                    allowed_hosts=[],
                ),
            )
