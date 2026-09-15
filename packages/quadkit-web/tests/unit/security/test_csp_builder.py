"""Tests for CSP builder.

Adapted from quadkit-security test suite; imports updated to
quadkit.web.security.* after HTTP middleware absorption in Task 3.
"""

from __future__ import annotations

import pytest

from quadkit.web.security.csp.builder import CSPPolicy


class TestCSPPolicy:
    """Tests for CSPPolicy."""

    def test_default_policy(self) -> None:
        """Should create a default policy."""
        policy = CSPPolicy()
        csp = policy.build()
        assert "default-src 'self'" in csp
        assert "script-src 'self'" in csp

    def test_strict_preset(self) -> None:
        """Should create a strict preset."""
        policy = CSPPolicy.strict()
        csp = policy.build()
        assert "script-src 'self'" in csp
        assert "object-src 'none'" in csp
        assert "upgrade-insecure-requests" in csp

    def test_relaxed_preset(self) -> None:
        """Should create a relaxed preset."""
        policy = CSPPolicy.relaxed()
        csp = policy.build()
        assert "https://cdn.jsdelivr.net" in csp
        assert "https://fonts.googleapis.com" in csp

    def test_api_only_preset(self) -> None:
        """Should create an API-only preset."""
        policy = CSPPolicy.api_only()
        csp = policy.build()
        assert "default-src 'none'" in csp
        assert "script-src 'none'" in csp
        assert "connect-src 'self'" in csp

    def test_custom_directive(self) -> None:
        """Should allow custom directives."""
        policy = CSPPolicy()
        policy.script_src.append("https://example.com")
        csp = policy.build()
        assert "https://example.com" in csp

    def test_report_uri(self) -> None:
        """Should include report-uri when set."""
        policy = CSPPolicy()
        policy.report_uri = "https://example.com/report"
        csp = policy.build()
        assert "report-uri https://example.com/report" in csp

    def test_upgrade_insecure_requests(self) -> None:
        """Should include upgrade-insecure-requests."""
        policy = CSPPolicy()
        policy.upgrade_insecure_requests = True
        csp = policy.build()
        assert "upgrade-insecure-requests" in csp

    def test_empty_directive_not_included(self) -> None:
        """Should not include empty directives."""
        policy = CSPPolicy()
        policy.default_src = []
        csp = policy.build()
        assert "default-src" not in csp
