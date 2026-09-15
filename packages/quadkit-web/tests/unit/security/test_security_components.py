"""HTTP security component tests for quadkit-web.

Covers: SecurityConfig, SecurityHeadersConfig, CORSMiddlewareFactory.
Adapted from quadkit-security unit tests; imports updated to
quadkit.web.security.* after HTTP middleware absorption in Task 3.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

from quadkit.web.security.config import (
    CORSConfig,
    SecurityConfig,
    SecurityHeadersConfig,
)
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


class TestSecurityHeadersConfig:
    """Test security headers configuration."""

    def test_config_creation(self) -> None:
        """Test headers config can be created."""
        config = SecurityHeadersConfig()
        assert config is not None

    def test_config_default_hsts_max_age(self) -> None:
        """Default HSTS max_age should be one year."""
        config = SecurityHeadersConfig()
        assert config.hsts_max_age == 31536000

    def test_config_with_custom_csp(self) -> None:
        """Test config with CSP string."""
        config = SecurityHeadersConfig(csp="default-src 'self'")
        assert "default-src" in (config.csp or "")

    def test_xss_protection_default(self) -> None:
        """XSS protection header should have a default value."""
        config = SecurityHeadersConfig()
        assert config.xss_protection is not None


class TestCSPConfigMerge:
    """Test CSPConfig merges partial directives with framework defaults."""

    def test_defaults_have_unsafe_inline_on_style_src_elem(self) -> None:
        """Defaults must include style-src-elem with 'unsafe-inline'."""
        from quadkit.web.security.config import CSPConfig

        config = CSPConfig()
        assert "'self'" in config.directives["style-src-elem"]
        assert "'unsafe-inline'" in config.directives["style-src-elem"]

    def test_partial_directives_fall_back_to_defaults(self) -> None:
        """A partial directives dict keeps defaults for omitted directives."""
        from quadkit.web.security.config import CSPConfig

        config = CSPConfig(directives={"style-src": "'self'"})
        assert config.directives["style-src"] == "'self'"
        assert "'self'" in config.directives["style-src-elem"]
        assert "'unsafe-inline'" in config.directives["style-src-elem"]
        assert config.directives["default-src"] == "'self'"

    def test_user_directives_override_defaults_per_key(self) -> None:
        """An explicit directive wins over the framework default for that key."""
        from quadkit.web.security.config import CSPConfig

        config = CSPConfig(directives={"default-src": "'none'"})
        assert config.directives["default-src"] == "'none'"
        assert "'unsafe-inline'" in config.directives["style-src-elem"]


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
        from quadkit.web.security.config import (
            SecurityHeadersConfig as CanonicalSecurityHeadersConfig,
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
        assert web_security.SecurityHeadersConfig is CanonicalSecurityHeadersConfig
        assert (
            web_security.SecurityHeadersMiddleware is CanonicalSecurityHeadersMiddleware
        )
