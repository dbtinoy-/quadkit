"""Unit tests for configuration domain"""

import pytest

from quadkit.web.config import (
    APIDocsConfig,
    RateLimitConfig,
    RateLimitRuleConfig,
    ServerConfig,
    StaticFileConfig,
    WebConfig,
    WebProviderConfig,
)


class TestServerConfig:
    """Test server configuration"""

    def test_server_config_creation(self):
        """Test server config with defaults"""
        config = ServerConfig()

        assert config.host == "0.0.0.0"
        assert config.port == 8000
        assert config.debug is False
        assert config.reload is False

    def test_server_config_custom_values(self):
        """Test server config with custom values"""
        config = ServerConfig(host="0.0.0.0", port=3000, debug=True, reload=True)

        assert config.host == "0.0.0.0"
        assert config.port == 3000
        assert config.debug is True
        assert config.reload is True

    def test_server_config_from_dict(self):
        """Test server config from dictionary"""
        data = {"host": "localhost", "port": 5000, "debug": True}

        config = ServerConfig(**data)
        assert config.host == "localhost"
        assert config.port == 5000
        assert config.debug is True

    def test_server_config_invalid_port(self):
        """Test server config validates port range"""
        with pytest.raises(ValueError, match="Invalid port"):
            ServerConfig(port=0)

        with pytest.raises(ValueError, match="Invalid port"):
            ServerConfig(port=70000)

    def test_server_config_empty_host(self):
        """Test server config validates empty host"""
        with pytest.raises(ValueError, match="Server host cannot be empty"):
            ServerConfig(host="")


class TestWebProviderConfig:
    """Test web provider configuration"""

    def test_web_provider_config_creation(self):
        """Test web provider config with defaults"""
        config = WebProviderConfig()

        assert config.openapi_title == "API"
        assert config.openapi_version == "1.0.0"
        assert config.middleware == []
        assert config.exception_filters == []

    def test_web_provider_config_custom_values(self):
        """Test web provider config with custom values"""
        config = WebProviderConfig(
            openapi_title="My API",
            openapi_version="2.0.0",
            middleware=["quadkit.web.middleware.cors.CORSMiddleware"],
            exception_filters=["quadkit.web.filters.DefaultExceptionFilter"],
        )

        assert config.openapi_title == "My API"
        assert config.openapi_version == "2.0.0"
        assert config.middleware == ["quadkit.web.middleware.cors.CORSMiddleware"]
        assert config.exception_filters == [
            "quadkit.web.filters.DefaultExceptionFilter",
        ]

    def test_web_provider_config_compression(self):
        """Test compression settings"""
        config = WebProviderConfig(compression_enabled=False)
        assert config.compression_enabled is False

        config_default = WebProviderConfig()
        assert config_default.compression_enabled is True


class TestStaticFileConfig:
    """Test static file configuration"""

    def test_static_file_config_defaults(self):
        """Test static file config default values"""
        config = StaticFileConfig()

        assert config.enabled is False
        assert config.directory == "static"
        assert config.prefix == "/static"
        assert config.html is False


class TestAPIDocsConfig:
    """Test API documentation configuration"""

    def test_api_docs_config_defaults(self):
        """Test API docs config default values"""
        config = APIDocsConfig()

        assert config.enabled is True
        assert config.provider == "both"

    def test_api_docs_default_requires_no_csp_domains(self):
        """Local (vendored) docs assets need no CSP additions (H-03)."""
        config = APIDocsConfig(enabled=True, provider="both")

        assert config.cdn_base is None
        assert config.get_required_domains() == {}

    def test_api_docs_cdn_base_allows_its_origin(self):
        """cdn_base opts into a CDN/mirror; its origin joins the CSP."""
        config = APIDocsConfig(
            enabled=True,
            cdn_base="https://unpkg.com/swagger-ui-dist@5.10.3",
        )
        domains = config.get_required_domains()

        assert domains["script-src"] == {"https://unpkg.com"}
        assert domains["style-src-elem"] == {"https://unpkg.com"}

    def test_api_docs_cdn_base_without_scheme(self):
        """Scheme-less cdn_base values default to https."""
        config = APIDocsConfig(enabled=True, cdn_base="mirror.internal/assets")
        domains = config.get_required_domains()

        assert domains["script-src"] == {"https://mirror.internal"}

    def test_api_docs_assets_mode(self):
        """assets_mode reports local/cdn/custom for the boot log."""
        assert APIDocsConfig().assets_mode() == "local"
        assert APIDocsConfig(cdn_base="https://x.test").assets_mode() == "cdn"
        assert (
            APIDocsConfig(cdn_base="https://x.test").assets_mode(
                swagger_js_url="https://y.test/b.js"
            )
            == "custom"
        )


class TestRateLimitRuleConfig:
    """Test rate limit rule configuration"""

    def test_rate_limit_rule_defaults(self):
        """Test rate limit rule default values"""
        rule = RateLimitRuleConfig()

        assert rule.requests == 100
        assert rule.window == 60
        assert rule.burst is None

    def test_effective_burst(self):
        """Test effective burst calculation"""
        rule = RateLimitRuleConfig(requests=50, burst=25)
        assert rule.effective_burst == 25

    def test_effective_burst_default(self):
        """Test effective burst defaults to requests"""
        rule = RateLimitRuleConfig(requests=50)
        assert rule.effective_burst == 50


class TestRateLimitConfig:
    """Test rate limiting configuration"""

    def test_rate_limit_defaults(self):
        """Test rate limit config default values"""
        config = RateLimitConfig()

        assert config.enabled is False
        assert config.default_limit == 100
        assert config.default_window == 60

    def test_rate_limit_get_rule_exact_match(self):
        """Test exact path match"""
        config = RateLimitConfig(rules={"/api": RateLimitRuleConfig(requests=200)})
        rule = config.get_rule("/api")

        assert rule is not None
        assert rule.requests == 200

    def test_rate_limit_get_rule_prefix_match(self):
        """Test longest prefix match"""
        config = RateLimitConfig(
            rules={
                "/api": RateLimitRuleConfig(requests=100),
                "/api/users": RateLimitRuleConfig(requests=50),
            }
        )
        rule = config.get_rule("/api/users/profile")

        assert rule is not None
        assert rule.requests == 50

    def test_rate_limit_get_rule_no_match(self):
        """Test no matching rule"""
        config = RateLimitConfig()
        rule = config.get_rule("/unknown")

        assert rule is None

    def test_rate_limit_get_rule_honours_path_boundary(self):
        """A '/api' rule must not match '/apifoo' (segment boundary)."""
        config = RateLimitConfig(rules={"/api": RateLimitRuleConfig(requests=100)})
        assert config.get_rule("/api") is not None
        assert config.get_rule("/api/users") is not None
        assert config.get_rule("/apifoo") is None
        assert config.get_rule("/api/v2") is not None


class TestWebConfig:
    """Test main web configuration"""

    def test_web_config_defaults(self):
        """Test web config default values"""
        config = WebConfig()

        assert config.name == "web"
        assert config.enabled is True
        assert config.server.host == "0.0.0.0"
        assert config.server.port == 8000

    def test_web_config_openapi_settings(self):
        """Test OpenAPI settings"""
        config = WebConfig(
            openapi_title="My API",
            openapi_version="2.0.0",
        )

        assert config.openapi_title == "My API"
        assert config.openapi_version == "2.0.0"

    def test_web_config_debug_routes(self):
        """Test debug routes configuration"""
        config = WebConfig(debug_routes=True)

        assert config.debug_routes is True

    def test_web_config_has_debug_routes_env_gate(self):
        """Test config-driven debug route registration gate."""
        config = WebConfig()
        assert hasattr(config, "enable_debug_routes_env_gate")
        assert config.enable_debug_routes_env_gate is False

    def test_web_config_auth_exclude_paths(self):
        """Test auth exclude paths"""
        config = WebConfig()

        assert "/health" in config.auth_exclude_paths
        assert "/docs" in config.auth_exclude_paths


class TestConfigValidation:
    """Test configuration validation"""

    def test_server_config_validation(self):
        """Test server config validates values"""
        config = ServerConfig(port=3000)
        assert config.port == 3000

        config = ServerConfig(host="192.168.1.1")
        assert config.host == "192.168.1.1"

    def test_web_provider_config_validation(self):
        """Test web provider config validation"""
        config = WebProviderConfig()
        assert config is not None

        full_config = WebProviderConfig(
            openapi_title="Test API",
            openapi_version="1.0.0",
            middleware=[],
            exception_filters=[],
            compression_enabled=False,
        )
        assert full_config.openapi_title == "Test API"

    def test_rate_limit_validation(self):
        """Test rate limit config validation"""
        with pytest.raises(ValueError, match="default_limit"):
            RateLimitConfig(enabled=True, default_limit=0)

        with pytest.raises(ValueError, match="default_window"):
            RateLimitConfig(enabled=True, default_window=0)
