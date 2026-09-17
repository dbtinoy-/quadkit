"""End-to-end pins for vendored docs assets (plans/09172026 H-03).

The default /docs and /redoc pages must make zero third-party requests:
assets are vendored in the package and served by the application under
/docs-static, the CSP header carries no 'unsafe-*' and no CDN origins, and
no CDN URL appears in the rendered HTML. CDN use is an explicit opt-in via
``web.api_docs.cdn_base`` (or per-asset URL overrides).
"""

from __future__ import annotations

from typing import Any

import pytest
from starlette.testclient import TestClient

from quadkit.app.base import Application
from quadkit.web.config import RateLimitConfig, WebConfig
from quadkit.web.di.provider import WebProvider

#: Third-party hosts that must never appear in default docs output.
FORBIDDEN_HOSTS = (
    "unpkg.com",
    "cdn.jsdelivr.net",
    "cdn.redoc.ly",
    "cdn.plot.ly",
    "fonts.googleapis.com",
    "fonts.gstatic.com",
)


async def _boot_docs_app(**config_overrides: Any) -> TestClient:
    """Boot a full application with docs routes and return a test client."""
    app = Application(name="docs-assets-test")

    async def _allow_all(request: Any) -> bool:
        return True

    web = WebProvider(
        web_config=WebConfig(
            rate_limit=RateLimitConfig(enabled=False),
            **config_overrides,
        ),
        debug_routes_auth=_allow_all,
    )

    await web.register(app.container)
    await web.boot(app.container)

    assert web.starlette is not None
    return TestClient(web.starlette)


@pytest.mark.asyncio
async def test_default_docs_html_uses_local_assets() -> None:
    client = await _boot_docs_app()

    response = client.get("/docs")
    assert response.status_code == 200
    html = response.text

    assert "/docs-static/swagger-ui-bundle.js" in html
    assert "/docs-static/swagger-ui-standalone-preset.js" in html
    assert "/docs-static/swagger-init.js" in html
    assert "/docs-static/swagger-ui.css" in html
    assert "/docs-static/docs.css" in html

    for host in FORBIDDEN_HOSTS:
        assert host not in html, f"default /docs references {host}"


@pytest.mark.asyncio
async def test_default_redoc_html_uses_local_assets() -> None:
    client = await _boot_docs_app()

    response = client.get("/redoc")
    assert response.status_code == 200
    html = response.text

    assert "/docs-static/redoc.standalone.js" in html
    for host in FORBIDDEN_HOSTS:
        assert host not in html, f"default /redoc references {host}"


@pytest.mark.asyncio
async def test_docs_html_has_no_inline_scripts_or_styles() -> None:
    """The pages need no 'unsafe-inline' in the CSP to render."""
    client = await _boot_docs_app()

    for path in ("/docs", "/redoc"):
        html = client.get(path).text
        assert "<style" not in html, f"{path} carries an inline <style>"
        # every <script> must be an external src reference
        assert "<script>" not in html
        assert "onclick=" not in html
        assert html.count("<script src=") >= 1


@pytest.mark.asyncio
async def test_default_docs_csp_is_strict() -> None:
    client = await _boot_docs_app()

    for path in ("/docs", "/redoc"):
        csp = client.get(path).headers.get("content-security-policy", "")
        assert csp, f"{path} has no CSP header"

        assert "unsafe-inline" not in csp
        assert "unsafe-eval" not in csp
        for host in FORBIDDEN_HOSTS:
            assert host not in csp, f"{path} CSP allows {host}"
        assert "connect-src 'self'" in csp


@pytest.mark.asyncio
async def test_vendored_assets_are_served() -> None:
    client = await _boot_docs_app()

    for asset, min_size in (
        ("swagger-ui-bundle.js", 100_000),
        ("swagger-ui-standalone-preset.js", 100_000),
        ("swagger-ui.css", 100_000),
        ("swagger-init.js", 200),
        ("docs.css", 100),
        ("redoc.standalone.js", 500_000),
        ("oauth2-redirect.html", 1_000),
    ):
        response = client.get(f"/docs-static/{asset}")
        assert response.status_code == 200, f"{asset} not served"
        assert len(response.content) >= min_size, f"{asset} too small"

    assert (
        "javascript"
        in client.get("/docs-static/swagger-ui-bundle.js").headers["content-type"]
    )
    assert "css" in client.get("/docs-static/swagger-ui.css").headers["content-type"]


@pytest.mark.asyncio
async def test_cdn_base_opt_in_uses_and_allows_cdn() -> None:
    client = await _boot_docs_app(
        api_docs={"cdn_base": "https://mirror.example.com/assets"}
    )

    docs = client.get("/docs")
    assert docs.status_code == 200
    assert "https://mirror.example.com/assets/swagger-ui-bundle.js" in docs.text

    redoc = client.get("/redoc")
    assert redoc.status_code == 200
    assert "https://mirror.example.com/assets/redoc.standalone.js" in redoc.text

    csp = docs.headers.get("content-security-policy", "")
    assert "https://mirror.example.com" in csp
    # the vendored mount is not needed in CDN mode
    assert "/docs-static/swagger-ui-bundle.js" not in docs.text


@pytest.mark.asyncio
async def test_explicit_asset_urls_take_precedence() -> None:
    client = await _boot_docs_app(swagger_js_url="/custom/bundle.js")

    docs = client.get("/docs")
    assert docs.status_code == 200
    assert "/custom/bundle.js" in docs.text
    assert "/docs-static/swagger-ui-bundle.js" not in docs.text
    # non-overridden assets still resolve locally
    assert "/docs-static/swagger-ui.css" in docs.text


@pytest.mark.asyncio
async def test_root_path_prefixes_local_assets() -> None:
    """Apps mounted under a sub-path link assets with the root_path."""
    app = Application(name="docs-root-path-test")

    async def _allow_all(request: Any) -> bool:
        return True

    web = WebProvider(
        web_config=WebConfig(rate_limit=RateLimitConfig(enabled=False)),
        debug_routes_auth=_allow_all,
    )
    await web.register(app.container)
    await web.boot(app.container)
    assert web.starlette is not None

    client = TestClient(web.starlette, root_path="/sub")
    response = client.get("/docs")
    assert response.status_code == 200
    assert 'src="/sub/docs-static/swagger-ui-bundle.js"' in response.text
