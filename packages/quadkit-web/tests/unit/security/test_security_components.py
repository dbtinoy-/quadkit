"""HTTP security component tests for quadkit-web.

Covers: SecurityConfig, HSTSConfig, CORSMiddlewareFactory.
Adapted from quadkit-security unit tests; imports updated to
quadkit.web.security.* after HTTP middleware absorption in Task 3.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

from quadkit.web.security.config import CORSConfig, HSTSConfig, SecurityConfig
from quadkit.web.security.cors.middleware import CORSMiddleware, CORSMiddlewareFactory


class TestSecurityConfig:
    """Test Security configuration."""

    def test_config_defaults(self) -> None:
        """Test default security configuration."""
        config = SecurityConfig()
        assert config.enable_csrf is True
        assert config.enable_cors is True

    def test_config_with_custom_values(self) -> None:
        """Test configuration with custom values."""
        config = SecurityConfig(
            enable_csrf=False,
            enable_cors=False,
        )
        assert config.enable_csrf is False
        assert config.enable_cors is False

    def test_config_has_cors_sub_config(self) -> None:
        """SecurityConfig must aggregate a CORSConfig sub-object."""
        config = SecurityConfig()
        assert isinstance(config.cors, CORSConfig)

    def test_config_has_csrf_sub_config(self) -> None:
        """SecurityConfig must aggregate a CSRFConfig sub-object."""
        from quadkit.web.security.config import CSRFConfig

        config = SecurityConfig()
        assert isinstance(config.csrf, CSRFConfig)


class TestHSTSConfig:
    """Test HSTS configuration."""

    def test_config_creation(self) -> None:
        """Test the HSTS config can be created."""
        assert HSTSConfig() is not None

    def test_default_hsts_max_age(self) -> None:
        """Default HSTS max_age should be one year."""
        assert HSTSConfig().max_age == 31536000

    def test_short_max_age_is_flagged_in_production(self) -> None:
        """Production validation warns below the one-year floor."""
        from quadkit.contracts.core.config import Environment

        config = HSTSConfig(max_age=600)
        assert [
            issue.field
            for issue in config.validate_for_environment(Environment.PRODUCTION)
        ] == ["hsts.max_age"]

    def test_enabled_is_opt_in(self) -> None:
        """HSTS stays off until an operator enables it."""
        assert HSTSConfig().enabled is False


class TestCSPConfigMerge:
    """Test CSPConfig merges partial directives with framework defaults."""

    def test_defaults_are_strict_no_unsafe_no_cdn(self) -> None:
        """Defaults must not include 'unsafe-*' or third-party CDN hosts."""
        from quadkit.web.security.config import CSPConfig

        config = CSPConfig()
        assert "'self'" in config.directives["style-src-elem"]
        assert "'unsafe-inline'" not in config.directives["style-src-elem"]
        assert "'unsafe-eval'" not in config.directives["script-src"]
        joined = " ".join(str(v) for v in config.directives.values())
        for host in (
            "unpkg.com",
            "cdn.jsdelivr.net",
            "cdn.redoc.ly",
            "cdn.plot.ly",
            "fonts.googleapis.com",
            "fonts.gstatic.com",
        ):
            assert host not in joined

    def test_partial_directives_fall_back_to_defaults(self) -> None:
        """A partial directives dict keeps defaults for omitted directives."""
        from quadkit.web.security.config import CSPConfig

        config = CSPConfig(directives={"style-src": "'self'"})
        assert config.directives["style-src"] == "'self'"
        assert "'self'" in config.directives["style-src-elem"]
        assert config.directives["default-src"] == "'self'"

    def test_user_directives_override_defaults_per_key(self) -> None:
        """An explicit directive wins over the framework default for that key."""
        from quadkit.web.security.config import CSPConfig

        config = CSPConfig(directives={"default-src": "'none'"})
        assert config.directives["default-src"] == "'none'"
        assert config.directives["style-src-elem"] == "'self'"


class TestCORSMiddlewareFactory:
    """Test the CORS middleware factory."""

    def test_factory_returns_middleware(self) -> None:
        """Factory wraps the provided ASGI application with configured headers."""
        factory = CORSMiddlewareFactory(
            config=CORSConfig(allowed_origins=["https://example.com"])
        )

        dummy_app = AsyncMock()
        middleware = factory(dummy_app)

        assert isinstance(middleware, CORSMiddleware)
        assert middleware.app is dummy_app

    def test_factory_default_config(self) -> None:
        """Factory should work without explicit config."""
        factory = CORSMiddlewareFactory()
        dummy_app = AsyncMock()
        middleware = factory(dummy_app)
        assert isinstance(middleware, CORSMiddleware)


class TestSecurityPackageExports:
    """Test the top-level quadkit.web.security public API."""

    def test_http_security_surface_is_reexported(self) -> None:
        """Top-level package should expose the absorbed HTTP security surface."""
        from quadkit.web import security as web_security
        from quadkit.web.middleware.security import (
            SecurityHeadersMiddleware as CanonicalSecurityHeadersMiddleware,
        )
        from quadkit.web.security.config import (
            CORSConfig as CanonicalCORSConfig,
        )
        from quadkit.web.security.config import (
            CrossOriginConfig as CanonicalCrossOriginConfig,
        )
        from quadkit.web.security.config import (
            CSPConfig as CanonicalCSPConfig,
        )
        from quadkit.web.security.config import (
            CSRFConfig as CanonicalCSRFConfig,
        )
        from quadkit.web.security.config import (
            HSTSConfig as CanonicalHSTSConfig,
        )
        from quadkit.web.security.config import (
            SecurityConfig as CanonicalSecurityConfig,
        )
        from quadkit.web.security.cors.middleware import (
            CORSMiddleware as CanonicalCORSMiddleware,
        )
        from quadkit.web.security.cors.middleware import (
            CORSMiddlewareFactory as CanonicalCORSMiddlewareFactory,
        )
        from quadkit.web.security.csp.builder import CSPPolicy as CanonicalCSPPolicy
        from quadkit.web.security.csrf.middleware import (
            CSRFProtectionMiddleware as CanonicalCSRFMiddleware,
        )

        assert web_security.CORSConfig is CanonicalCORSConfig
        assert web_security.CORSMiddleware is CanonicalCORSMiddleware
        assert web_security.CORSMiddlewareFactory is CanonicalCORSMiddlewareFactory
        assert web_security.CSPConfig is CanonicalCSPConfig
        assert web_security.CSPPolicy is CanonicalCSPPolicy
        assert web_security.CSRFConfig is CanonicalCSRFConfig
        assert web_security.CSRFProtectionMiddleware is CanonicalCSRFMiddleware
        assert web_security.CrossOriginConfig is CanonicalCrossOriginConfig
        assert web_security.HSTSConfig is CanonicalHSTSConfig
        assert web_security.SecurityConfig is CanonicalSecurityConfig
        assert (
            web_security.SecurityHeadersMiddleware is CanonicalSecurityHeadersMiddleware
        )
