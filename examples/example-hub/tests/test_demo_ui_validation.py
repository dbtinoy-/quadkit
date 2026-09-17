"""Validate every demo's UI serves correctly — pages, static assets, structure."""

from __future__ import annotations

import httpx
import pytest

registry_mod = pytest.importorskip("example_hub.services.registry")

# Every test in this module drives the running demo fleet over HTTP at
# 127.0.0.1:7000, so they need `make demos-up` first. Without the marker they
# fail with ConnectError in any ordinary run; the demo gate (`make test-demos`)
# already filters on `-m "not integration"`, and this is what makes that
# filter actually cover them.
pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def registry() -> registry_mod.ServiceRegistry:
    return registry_mod.ServiceRegistry()


@pytest.fixture(scope="module")
def client() -> httpx.Client:
    return httpx.Client(follow_redirects=True, timeout=10)


def console_services(registry: registry_mod.ServiceRegistry) -> list:
    """Demos with a browser console UI.

    The seven starter templates are API-only by design (starter minimalism):
    they serve a JSON index route at ``/`` instead of the demo-nav shell, so
    the shell/asset assertions below apply to the console demos only.
    """
    return [svc for svc in registry.web_services() if svc.group != "starter"]


class TestDemoUIValidation:
    """Validate each demo's UI against its code."""

    def test_all_demos_return_200(self, registry: registry_mod.ServiceRegistry, client: httpx.Client) -> None:
        """Every web demo must serve its index page with HTTP 200."""
        for svc in registry.web_services():
            resp = client.get(f"http://127.0.0.1:7000/examples/{svc.slug}/")
            assert resp.status_code == 200, f"{svc.slug} returned {resp.status_code}"

    def test_starter_demos_serve_json_index(self, registry: registry_mod.ServiceRegistry, client: httpx.Client) -> None:
        """Starter templates are API-only: their index is a JSON descriptor."""
        starters = [svc for svc in registry.web_services() if svc.group == "starter"]
        assert len(starters) == 7
        for svc in starters:
            resp = client.get(f"http://127.0.0.1:7000/examples/{svc.slug}/")
            assert resp.status_code == 200, f"{svc.slug} returned {resp.status_code}"
            body = resp.json()
            assert body["demo"] == svc.slug, f"{svc.slug} index body wrong: {body}"

    def test_all_demos_have_nav(self, registry: registry_mod.ServiceRegistry, client: httpx.Client) -> None:
        """Every demo must have a navigation bar."""
        for svc in console_services(registry):
            resp = client.get(f"http://127.0.0.1:7000/examples/{svc.slug}/")
            assert "<nav" in resp.text, f"{svc.slug} missing <nav>"

    def test_all_demos_have_brand(self, registry: registry_mod.ServiceRegistry, client: httpx.Client) -> None:
        """Every demo must have a nav-brand link."""
        for svc in console_services(registry):
            resp = client.get(f"http://127.0.0.1:7000/examples/{svc.slug}/")
            assert 'class="nav-brand"' in resp.text, f"{svc.slug} missing nav-brand"

    def test_all_demos_serve_css(self, registry: registry_mod.ServiceRegistry, client: httpx.Client) -> None:
        """Every demo must serve its stylesheet."""
        for svc in console_services(registry):
            resp = client.get(f"http://127.0.0.1:7000/examples/{svc.slug}/static/style.css")
            assert resp.status_code == 200, f"{svc.slug} CSS returned {resp.status_code}"
            assert "text/css" in resp.headers.get("content-type", ""), f"{svc.slug} CSS content-type wrong"

    def test_all_demos_serve_js(self, registry: registry_mod.ServiceRegistry, client: httpx.Client) -> None:
        """Every demo must serve its JavaScript (app.js or dashboard.js)."""
        for svc in console_services(registry):
            resp_app = client.get(f"http://127.0.0.1:7000/examples/{svc.slug}/static/app.js")
            resp_dash = client.get(f"http://127.0.0.1:7000/examples/{svc.slug}/static/dashboard.js")
            assert resp_app.status_code == 200 or resp_dash.status_code == 200, \
                f"{svc.slug} no JS found (app.js={resp_app.status_code}, dashboard.js={resp_dash.status_code})"

    def test_all_demos_serve_logo(self, registry: registry_mod.ServiceRegistry, client: httpx.Client) -> None:
        """Every demo must serve logo.png."""
        for svc in console_services(registry):
            resp = client.get(f"http://127.0.0.1:7000/examples/{svc.slug}/static/logo.png")
            assert resp.status_code == 200, f"{svc.slug} logo returned {resp.status_code}"

    def test_all_demos_serve_icon(self, registry: registry_mod.ServiceRegistry, client: httpx.Client) -> None:
        """Every demo must serve icon.png (favicon)."""
        for svc in console_services(registry):
            resp = client.get(f"http://127.0.0.1:7000/examples/{svc.slug}/static/icon.png")
            assert resp.status_code == 200, f"{svc.slug} icon returned {resp.status_code}"

    def test_all_demos_have_favicon_link(self, registry: registry_mod.ServiceRegistry, client: httpx.Client) -> None:
        """Every demo must have a favicon link tag."""
        for svc in console_services(registry):
            resp = client.get(f"http://127.0.0.1:7000/examples/{svc.slug}/")
            assert 'rel="icon"' in resp.text, f"{svc.slug} missing favicon link"

    def test_auth_demos_have_auth_shell(self, client: httpx.Client) -> None:
        """Auth demos must have the auth-shell container."""
        auth_slugs = ["auth-web", "auth-rbac", "auth-apikeys", "auth-mfa"]
        for slug in auth_slugs:
            resp = client.get(f"http://127.0.0.1:7000/examples/{slug}/")
            assert 'class="auth-shell"' in resp.text, f"{slug} missing auth-shell"
            assert 'class="auth-content"' in resp.text, f"{slug} missing auth-content"

    def test_auth_demos_have_card(self, client: httpx.Client) -> None:
        """Auth demos must have a card container."""
        auth_slugs = ["auth-web", "auth-rbac", "auth-apikeys", "auth-mfa"]
        for slug in auth_slugs:
            resp = client.get(f"http://127.0.0.1:7000/examples/{slug}/")
            assert 'class="card"' in resp.text, f"{slug} missing card"

    def test_hub_serves_all_demos(self, client: httpx.Client) -> None:
        """Hub must list all demos in its API."""
        resp = client.get("http://127.0.0.1:7000/api/status")
        assert resp.status_code == 200
        data = resp.json()
        slugs = {s["slug"] for s in data["services"]}
        registry = registry_mod.ServiceRegistry()
        expected = {s.slug for s in registry.web_services()}
        assert slugs == expected, f"Missing: {expected - slugs}, Extra: {slugs - expected}"

    def test_hub_serves_favicon(self, client: httpx.Client) -> None:
        """Hub must serve its own favicon."""
        resp = client.get("http://127.0.0.1:7000/static/icon.png")
        assert resp.status_code == 200

    def test_hub_has_group_filters(self, client: httpx.Client) -> None:
        """Hub must have Starter/Standard/Multi-module filter buttons."""
        resp = client.get("http://127.0.0.1:7000/")
        assert 'data-f="starter"' in resp.text
        assert 'data-f="standard"' in resp.text
        assert 'data-f="multi-module"' in resp.text

    def test_demo_nav_css_identical(self, registry: registry_mod.ServiceRegistry, client: httpx.Client) -> None:
        """All demos must share identical nav CSS rules."""
        import re, hashlib

        nav_rules: dict[str, str] = {}
        for svc in console_services(registry):
            resp = client.get(f"http://127.0.0.1:7000/examples/{svc.slug}/static/style.css")
            rules = "\n".join(
                re.findall(r"(\.demo-nav[^{]*\{[^}]*\}|\.nav-[^{]*\{[^}]*\})", resp.text)
            )
            nav_rules[svc.slug] = rules

        hashes = {hashlib.md5(v.encode()).hexdigest() for v in nav_rules.values()}
        assert len(hashes) == 1, f"Nav CSS differs across demos: {hashes}"

    def test_all_demos_serve_tokens_css(
        self, registry: registry_mod.ServiceRegistry, client: httpx.Client
    ) -> None:
        """Every demo must serve the shared design-token stylesheet."""
        for svc in console_services(registry):
            resp = client.get(f"http://127.0.0.1:7000/examples/{svc.slug}/static/tokens.css")
            assert resp.status_code == 200, f"{svc.slug} tokens.css returned {resp.status_code}"
            assert "text/css" in resp.headers.get("content-type", ""), f"{svc.slug} tokens.css content-type wrong"

    def test_all_demos_serve_theme_toggle_js(
        self, registry: registry_mod.ServiceRegistry, client: httpx.Client
    ) -> None:
        """Every demo must serve the shared light/dark theme-toggle script."""
        for svc in console_services(registry):
            resp = client.get(f"http://127.0.0.1:7000/examples/{svc.slug}/static/theme-toggle.js")
            assert resp.status_code == 200, f"{svc.slug} theme-toggle.js returned {resp.status_code}"

    def test_all_demos_link_tokens_before_own_stylesheet(
        self, registry: registry_mod.ServiceRegistry, client: httpx.Client
    ) -> None:
        """Every demo's <head> must link tokens.css before its own style.css,
        and wire the theme bootstrap script + toggle script, so a demo can
        never silently lose the shared design-token contract."""
        for svc in console_services(registry):
            resp = client.get(f"http://127.0.0.1:7000/examples/{svc.slug}/")
            html = resp.text
            # The hub rewrites "/static/..." to "/examples/<slug>/static/..."
            # in served HTML, so match the suffix rather than the raw path.
            tokens_idx = html.find('static/tokens.css"')
            style_idx = html.find('static/style.css"')
            assert tokens_idx != -1, f"{svc.slug} missing tokens.css link"
            assert style_idx != -1, f"{svc.slug} missing style.css link"
            assert tokens_idx < style_idx, f"{svc.slug} tokens.css must be linked before style.css"
            assert 'data-theme' in html, f"{svc.slug} missing theme bootstrap script"
            assert 'static/theme-toggle.js' in html, f"{svc.slug} missing theme-toggle.js script tag"

    def test_all_demos_use_canonical_accent(
        self, registry: registry_mod.ServiceRegistry, client: httpx.Client
    ) -> None:
        """Every demo's design tokens must come from the shared, canonical
        ``tokens.css`` (a single lime brand accent, identical in the
        light/dark palette) — never redefined locally per demo.

        Regression guard for a 2026-09-10 drift where three demos shipped a
        one-off blue accent (``#2563eb``) instead of the canonical token,
        superseded by the 2026-09-10 design-token migration that moved all
        color tokens out of per-demo style.css into examples/shared so this
        class of drift can no longer happen at all.
        """
        offenders: list[str] = []
        for svc in console_services(registry):
            resp = client.get(f"http://127.0.0.1:7000/examples/{svc.slug}/static/style.css")
            if resp.status_code != 200:
                continue
            css = resp.text
            # Demos must not redefine :root color tokens locally — that's
            # exactly the drift vector this test exists to prevent.
            if ":root" in css:
                offenders.append(svc.slug)

        assert not offenders, f"Demo(s) redefining :root tokens locally (should come from shared tokens.css): {offenders}"

    def test_shared_tokens_define_canonical_brand_palette(self, client: httpx.Client) -> None:
        """The shared tokens.css must define one identical brand accent
        (lime #c8ff00) for both the light and dark palettes — the accent
        color itself never changes between themes, only the surfaces/text
        around it (and --accent-text, which is a darkened same-hue variant
        used specifically where the accent paints text on a light
        surface, since pure lime has ~1.2:1 contrast against white)."""
        resp = client.get("http://127.0.0.1:7000/static/tokens.css")
        assert resp.status_code == 200
        css = resp.text
        assert '[data-theme="dark"]' in css, "dark palette must be gated by [data-theme=dark]"
        assert css.count("--accent: #c8ff00;") == 2, "the brand accent must be the identical lime in both light and dark palettes"
        assert "--accent-text: #4d6100;" in css, "light-mode accent-as-text must be a darkened same-hue variant for readability"
        assert "--accent-text: #c8ff00;" in css, "dark-mode accent-as-text can be the lime itself (already high-contrast there)"
