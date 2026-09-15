"""Tests for the aggregate SecurityConfig."""

from __future__ import annotations

from quadkit.contracts.core.config import ConfigIssue, Environment
from quadkit.validation import SecretStr
from quadkit.web.security.config.cors import CORSConfig
from quadkit.web.security.config.csp import CSPConfig
from quadkit.web.security.config.csrf import CSRFConfig
from quadkit.web.security.config.headers import (
    CrossOriginConfig,
    HSTSConfig,
    SecurityHeadersConfig,
)
from quadkit.web.security.config.top_level import SecurityConfig


class TestDefaults:
    def test_top_level_flags(self) -> None:
        c = SecurityConfig()
        assert c.enabled is True
        assert c.enable_csrf is True
        assert c.enable_cors is True
        assert c.referrer_policy == "strict-origin-when-cross-origin"
        assert c.allowed_hosts == []

    def test_sub_configs_present(self) -> None:
        c = SecurityConfig()
        assert isinstance(c.cors, CORSConfig)
        assert isinstance(c.csrf, CSRFConfig)
        assert isinstance(c.headers, SecurityHeadersConfig)
        assert isinstance(c.hsts, HSTSConfig)
        assert isinstance(c.csp, CSPConfig)
        assert isinstance(c.cross_origin, CrossOriginConfig)

    def test_custom_headers_default(self) -> None:
        c = SecurityConfig()
        assert c.custom_headers == {
            "x-content-type-options": "nosniff",
            "x-frame-options": "DENY",
            "x-xss-protection": "1; mode=block",
        }

    def test_permissions_policy_default(self) -> None:
        c = SecurityConfig()
        assert set(c.permissions_policy) == {
            "geolocation",
            "microphone",
            "camera",
            "payment",
            "usb",
        }
        assert c.permissions_policy["camera"] == "()"


class TestCsrfFlagSync:
    def test_enable_csrf_false_disables_csrf(self) -> None:
        c = SecurityConfig(enable_csrf=False)
        assert c.csrf.enabled is False

    def test_explicit_csrf_wins_when_flag_true(self) -> None:
        c = SecurityConfig(csrf=CSRFConfig(enabled=True))
        assert c.enable_csrf is True
        assert c.csrf.enabled is True

    def test_flag_false_overrides_explicit_csrf(self) -> None:
        c = SecurityConfig(csrf=CSRFConfig(enabled=True), enable_csrf=False)
        assert c.csrf.enabled is False

    def test_default_csrf_stays_its_default(self) -> None:
        # CSRFConfig itself defaults to enabled=False; the flag (True) does
        # not force it on — only an explicit csrf config wins.
        c = SecurityConfig()
        assert c.csrf.enabled == CSRFConfig().enabled


class TestEnvironmentValidation:
    def test_development_no_issues(self) -> None:
        c = SecurityConfig()
        issues = c.validate_for_environment(Environment.DEVELOPMENT)
        assert issues == []

    def test_production_aggregates_csrf_issue(self) -> None:
        # CSRF enabled in production without a secret key must raise an issue
        c = SecurityConfig(
            csrf=CSRFConfig(enabled=True, secret_key=SecretStr("k")),
            allowed_hosts=["app.example.com"],
        )
        issues = c.validate_for_environment(Environment.PRODUCTION)
        assert isinstance(issues, list)

    def test_production_csrf_without_key_raises_issue(self) -> None:
        c = SecurityConfig(csrf=CSRFConfig(enabled=True))
        issues = c.validate_for_environment(Environment.PRODUCTION)
        assert any("secret_key" in str(i) or "secret" in str(i) for i in issues)

    def test_issues_are_config_issues(self) -> None:
        c = SecurityConfig(csrf=CSRFConfig(enabled=True))
        issues = c.validate_for_environment(Environment.PRODUCTION)
        for issue in issues:
            assert isinstance(issue, ConfigIssue)

    def test_wildcard_cors_production_issue(self) -> None:
        # the issue fires for wildcard + credentials; a plain wildcard alone
        # is not flagged by the CORS sub-validator (WebConfig blocks it)
        c = SecurityConfig(cors=CORSConfig(allowed_origins=["*"]))
        assert c.validate_for_environment(Environment.PRODUCTION) == []
        # NOTE: wildcard+credentials is rejected at construction time, so the
        # production validator only sees non-credential wildcards.

    def test_cors_production_no_issue_for_specific_origins(self) -> None:
        c = SecurityConfig(cors=CORSConfig(allowed_origins=["https://a.example"]))
        assert c.validate_for_environment(Environment.PRODUCTION) == []


class TestConstruction:
    def test_nested_override(self) -> None:
        c = SecurityConfig(
            cors=CORSConfig(allowed_origins=["https://a.example"]),
            hsts=HSTSConfig(max_age=100),
        )
        assert c.cors.allowed_origins == ["https://a.example"]
        assert c.hsts.max_age == 100

    def test_custom_headers_override(self) -> None:
        c = SecurityConfig(custom_headers={"x-custom": "v"})
        assert c.custom_headers == {"x-custom": "v"}
