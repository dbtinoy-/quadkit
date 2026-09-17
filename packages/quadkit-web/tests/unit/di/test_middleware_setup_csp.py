"""Tests for automatic CSP configuration of API documentation.

Covers (plans/09172026 H-03):

- The default WebConfig keeps the CSP strict: docs assets are vendored and
  served by the application itself, so no CDN origins are merged and the
  boot log reports the ``local`` assets mode.
- Setting ``api_docs.cdn_base`` opts into a CDN: its origin is merged into
  the CSP for scripts and styles.
- Explicitly disabling ``api_docs`` leaves the CSP untouched.
- Pre-existing directives (str or set) are preserved during the merge.
"""

from __future__ import annotations

import pytest

from quadkit.web.config import WebConfig
from quadkit.web.di.middleware_setup import MiddlewareSetup


@pytest.mark.asyncio
async def test_default_config_keeps_csp_strict_for_docs() -> None:
    """The default WebConfig adds no CDN domains and stays local."""
    config = WebConfig()
    setup = MiddlewareSetup(config=config)

    await setup._configure_csp()

    directives = config.security.csp.directives
    assert "https://unpkg.com" not in directives["script-src"]
    assert "https://cdn.redoc.ly" not in directives["script-src"]
    assert "https://fonts.googleapis.com" not in directives["style-src"]
    assert "'unsafe-eval'" not in directives["script-src"]
    assert "'unsafe-inline'" not in directives["style-src-elem"]
    assert "connect-src" not in directives or "https:" not in directives["connect-src"]


@pytest.mark.asyncio
async def test_cdn_base_merges_origin_into_csp() -> None:
    """Opting into a CDN via cdn_base allows exactly that origin."""
    config = WebConfig()
    config.api_docs.cdn_base = "https://mirror.example.com/assets"
    setup = MiddlewareSetup(config=config)

    await setup._configure_csp()

    directives = config.security.csp.directives
    assert "https://mirror.example.com" in directives["script-src"]
    assert "https://mirror.example.com" in directives["script-src-elem"]
    assert "https://mirror.example.com" in directives["style-src"]
    assert "https://unpkg.com" not in directives["script-src"]


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
    """Custom str/set directives keep their values while CDN origins are added."""
    config = WebConfig()
    config.api_docs.cdn_base = "https://mirror.example.com"
    config.security.csp.directives = {
        "script-src": "'self' 'unsafe-inline'",
        "style-src": {"'self'", "https://cdn.jsdelivr.net"},
    }
    setup = MiddlewareSetup(config=config)

    await setup._configure_csp()

    directives = config.security.csp.directives
    assert "'self' 'unsafe-inline'" in directives["script-src"]
    assert "https://mirror.example.com" in directives["script-src"]
    assert "'self'" in directives["style-src"]
    assert "https://cdn.jsdelivr.net" in directives["style-src"]
    assert "https://mirror.example.com" in directives["style-src"]
