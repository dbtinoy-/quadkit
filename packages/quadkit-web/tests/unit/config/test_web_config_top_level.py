"""Tests for the top-level WebConfig hierarchy and production validation."""

from __future__ import annotations

import pytest

from quadkit.contracts.core.config import Environment
from quadkit.validation import SecretStr
from quadkit.web.config.top_level import WebConfig
from quadkit.web.security.config import CORSConfig


class TestDefaults:
    def test_identity(self) -> None:
        c = WebConfig()
        assert c.name == "web"
        assert c.enabled is True
        assert c.env is None

    def test_nested_defaults(self) -> None:
        c = WebConfig()
        assert c.server is not None
        assert c.security.csrf.enabled is True
        assert "/health" in c.security.csrf.excluded_paths
        assert "http://localhost:3000" in c.cors.allowed_origins
        assert c.static is not None
        assert c.rate_limit is not None
        assert c.api_docs is not None
        assert c.role_guard is not None

    def test_openapi_defaults(self) -> None:
        c = WebConfig()
        assert c.openapi_title == "API"
        assert c.openapi_version == "1.0.0"
        assert c.redoc_url == "/redoc"
        assert c.compression_enabled is True

    def test_debug_and_auth_defaults(self) -> None:
        c = WebConfig()
        assert c.debug_routes is False
        assert c.enable_debug_routes_env_gate is False
        assert c.debug_routes_token is None
        assert c.enable_identity_resolution is False
        assert c.enable_auth is False

    def test_max_body_size_default(self) -> None:
        assert WebConfig().max_body_size == 10 * 1024 * 1024

    def test_auth_exclude_paths_default(self) -> None:
        c = WebConfig()
        assert "/health" in c.auth_exclude_paths
        assert "/docs" in c.auth_exclude_paths
        assert "/openapi.json" in c.auth_exclude_paths


class TestConstruction:
    def test_env_assignment(self) -> None:
        c = WebConfig(env=Environment.STAGING)
        assert c.environment is Environment.STAGING

    def test_nested_override(self) -> None:
        c = WebConfig(cors=CORSConfig(allowed_origins=["https://example.com"]))
        assert c.cors.allowed_origins == ["https://example.com"]

    def test_secret_str_roundtrip(self) -> None:
        c = WebConfig(debug_routes_token=SecretStr("tok"))
        assert c.debug_routes_token is not None
        assert c.debug_routes_token.get_secret_value() == "tok"

    def test_max_body_size_rejects_zero(self) -> None:
        with pytest.raises(ValueError, match="greater than or equal to 1"):
            WebConfig(max_body_size=0)

    def test_extra_keys_preserved(self) -> None:
        # NOTE: the config base retains unknown keys (model_extra) despite the
        # extra=ignore declaration — documented here as the actual behavior.
        c = WebConfig(not_a_real_field=1)  # type: ignore[call-arg]
        assert getattr(c, "model_extra", None) == {"not_a_real_field": 1}


class TestWildcardCORS:
    def test_wildcard_with_credentials_always_blocked(self) -> None:
        # CORSConfig itself rejects the wildcard+credentials combination
        with pytest.raises(ValueError, match="CORS misconfiguration"):
            CORSConfig(allowed_origins=["*"], allow_credentials=True)

    def test_wildcard_without_credentials_ok(self) -> None:
        c = WebConfig(cors=CORSConfig(allowed_origins=["*"]))
        assert "*" in c.cors.allowed_origins

    def test_specific_origins_with_credentials_ok(self) -> None:
        c = WebConfig(
            cors=CORSConfig(
                allowed_origins=["https://a.example"],
                allow_credentials=True,
            )
        )
        assert c.cors.allow_credentials is True


class TestProductionGuards:
    def test_production_wildcard_cors_blocked(self) -> None:
        with pytest.raises(ValueError, match="PRODUCTION"):
            WebConfig(
                env=Environment.PRODUCTION,
                cors=CORSConfig(allowed_origins=["*"]),
            )

    def test_production_csrf_disabled_blocked(self) -> None:
        from quadkit.web.security.config import CSRFConfig, SecurityConfig

        with pytest.raises(ValueError, match="CSRF"):
            WebConfig(
                env=Environment.PRODUCTION,
                security=SecurityConfig(csrf=CSRFConfig(enabled=False)),
            )

    def test_production_csrf_without_key_blocked(self) -> None:
        with pytest.raises(ValueError, match="secret_key"):
            WebConfig(env=Environment.PRODUCTION)

    def test_production_missing_allowed_hosts_blocked(self) -> None:
        from quadkit.web.security.config import CSRFConfig, SecurityConfig

        with pytest.raises(ValueError, match="allowed_hosts"):
            WebConfig(
                env=Environment.PRODUCTION,
                security=SecurityConfig(
                    csrf=CSRFConfig(enabled=True, secret_key=SecretStr("k")),
                ),
            )

    def test_production_hsts_forced_on(self) -> None:
        from quadkit.web.security.config import CSRFConfig, SecurityConfig

        c = WebConfig(
            env=Environment.PRODUCTION,
            security=SecurityConfig(
                csrf=CSRFConfig(enabled=True, secret_key=SecretStr("k")),
                allowed_hosts=["app.example.com"],
            ),
        )
        assert c.security.hsts.enabled is True

    def test_non_production_allows_wildcard(self) -> None:
        c = WebConfig(
            env=Environment.DEVELOPMENT,
            cors=CORSConfig(allowed_origins=["*"]),
        )
        assert "*" in c.cors.allowed_origins

    def test_full_production_valid_config(self) -> None:
        from quadkit.web.security.config import CSRFConfig, SecurityConfig

        c = WebConfig(
            env=Environment.PRODUCTION,
            cors=CORSConfig(allowed_origins=["https://app.example.com"]),
            security=SecurityConfig(
                csrf=CSRFConfig(enabled=True, secret_key=SecretStr("s")),
                allowed_hosts=["app.example.com"],
            ),
        )
        assert c.environment is Environment.PRODUCTION
        assert c.security.hsts.enabled is True


class TestAPIDocsServing:
    """The docs switch resolves against the environment (S-02).

    ``web.api_docs.enabled`` is tri-state: unset serves the documentation
    outside production, withheld in production until an operator opts in;
    ``true``/``false`` decide explicitly in every environment.
    """

    @staticmethod
    def _production(enabled: bool | None = None) -> WebConfig:
        """A production config that passes the production security guards."""
        from quadkit.web.security.config import CSRFConfig, SecurityConfig

        config = WebConfig(
            env=Environment.PRODUCTION,
            security=SecurityConfig(
                csrf=CSRFConfig(enabled=True, secret_key=SecretStr("k")),
                allowed_hosts=["app.example.com"],
            ),
        )
        if enabled is not None:
            config.api_docs.enabled = enabled
        return config

    def test_default_serves_outside_production(self) -> None:
        assert WebConfig().api_docs_enabled is True
        assert WebConfig(env=Environment.TEST).api_docs_enabled is True
        assert WebConfig(env=Environment.STAGING).api_docs_enabled is True

    def test_default_withholds_in_production(self) -> None:
        assert self._production().api_docs_enabled is False

    def test_explicit_opt_in_serves_in_production(self) -> None:
        assert self._production(enabled=True).api_docs_enabled is True

    def test_explicit_off_withholds_outside_production(self) -> None:
        from quadkit.web.config import APIDocsConfig

        config = WebConfig(api_docs=APIDocsConfig(enabled=False))
        assert config.api_docs_enabled is False
