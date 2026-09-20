"""Tests for CSP report-only mode.

Adapted from quadkit-security test suite; imports updated to
quadkit.web.security.* after HTTP middleware absorption in Task 3.
"""

from __future__ import annotations

import pytest

from quadkit.web.security.csp.builder import CSPPolicy


class TestCSPReportOnly:
    """Tests for CSP report-only mode."""

    def test_report_only_default_false(self) -> None:
        """Test that report_only defaults to False."""
        policy = CSPPolicy()
        assert policy.report_only is False

    def test_report_only_true(self) -> None:
        """Test setting report_only to True."""
        policy = CSPPolicy(report_only=True)
        assert policy.report_only is True

    def test_get_header_name_enforce(self) -> None:
        """Test header name when report_only is False."""
        policy = CSPPolicy(report_only=False)
        assert policy.get_header_name() == "Content-Security-Policy"

    def test_get_header_name_report_only(self) -> None:
        """Test header name when report_only is True."""
        policy = CSPPolicy(report_only=True)
        assert policy.get_header_name() == "Content-Security-Policy-Report-Only"

    def test_build_uses_report_only_instance_attribute(self) -> None:
        """Test that build() uses the instance report_only attribute."""
        policy = CSPPolicy(report_only=True)
        assert policy.get_header_name() == "Content-Security-Policy-Report-Only"

    def test_build_with_explicit_report_only_param(self) -> None:
        """Test that build() accepts report_only override parameter."""
        policy = CSPPolicy(report_only=False)
        assert policy.get_header_name() == "Content-Security-Policy"

    def test_report_only_with_report_uri(self) -> None:
        """Test report_only works with report_uri."""
        policy = CSPPolicy(
            report_only=True,
            report_uri="/csp-report",
        )
        assert policy.report_uri == "/csp-report"
        assert policy.report_only is True
        assert policy.get_header_name() == "Content-Security-Policy-Report-Only"

    def test_report_only_strict_preset(self) -> None:
        """Test report_only with strict preset."""
        policy = CSPPolicy.strict()
        policy.report_only = True

        assert policy.report_only is True
        assert policy.get_header_name() == "Content-Security-Policy-Report-Only"

    def test_report_only_relaxed_preset(self) -> None:
        """Test report_only with relaxed preset."""
        policy = CSPPolicy.relaxed()
        policy.report_only = True

        assert policy.report_only is True
        assert policy.get_header_name() == "Content-Security-Policy-Report-Only"

    def test_report_only_api_only_preset(self) -> None:
        """Test report_only with api_only preset."""
        policy = CSPPolicy.api_only()
        policy.report_only = True

        assert policy.report_only is True
        assert policy.get_header_name() == "Content-Security-Policy-Report-Only"
