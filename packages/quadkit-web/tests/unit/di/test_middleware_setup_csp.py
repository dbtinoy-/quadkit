"""Tests for automatic CSP configuration of API documentation.

Covers:
- ``MiddlewareSetup._configure_csp`` merges the Swagger/ReDoc CDN domains
  into the CSP by default (``APIDocsConfig.enabled`` defaults to True), so
  ``/docs`` and ``/redoc`` render for every quadkit-web application.
- Explicitly disabling ``api_docs`` leaves the CSP untouched.
- Pre-existing directives (str or set) are preserved during the merge.
"""

from __future__ import annotations

import pytest

from quadkit.web.config import WebConfig
from quadkit.web.di.middleware_setup import MiddlewareSetup


@pytest.mark.asyncio
async def test_default_config_auto_configures_csp_for_docs() -> None:
    """The default WebConfig merges docs CDN domains into the CSP."""
    config = WebConfig()
    setup = MiddlewareSetup(config=config)

    await setup._configure_csp()

    directives = config.security.csp.directives
    assert "https://unpkg.com" in directives["script-src"]
    assert "https://unpkg.com" in directives["style-src"]
    assert "https://cdn.redoc.ly" in directives["script-src"]


@pytest.mark.asyncio
async def test_api_docs_disabled_skips_csp_merge() -> None:
    """Explicitly disabling api_docs leaves a strict custom CSP untouched."""
    config = WebConfig()
    config.api_docs.enabled = False
    config.security.csp.directives = {
        "script-src": "'self'",
        "style-src": "'self'",
    }
    setup = MiddlewareSetup(config=config)

    await setup._configure_csp()

    directives = config.security.csp.directives
    assert directives["script-src"] == "'self'"
    assert "https://unpkg.com" not in directives["script-src"]


@pytest.mark.asyncio
async def test_existing_directive_values_are_preserved() -> None:
    """Custom str/set directives keep their values while docs domains are added."""
    config = WebConfig()
    config.security.csp.directives = {
        "script-src": "'self' 'unsafe-inline'",
        "style-src": {"'self'", "https://cdn.jsdelivr.net"},
    }
    setup = MiddlewareSetup(config=config)

    await setup._configure_csp()

    directives = config.security.csp.directives
    assert "'self' 'unsafe-inline'" in directives["script-src"]
    assert "https://unpkg.com" in directives["script-src"]
    assert "'self'" in directives["style-src"]
    assert "https://cdn.jsdelivr.net" in directives["style-src"]
    assert "https://unpkg.com" in directives["style-src"]
