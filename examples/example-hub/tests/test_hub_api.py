"""Tests for the demo hub registry, HTML rewriting, and API surface."""

from __future__ import annotations

import pytest

registry_mod = pytest.importorskip("example_hub.services.registry")
subsite_mod = pytest.importorskip("example_hub.subsite")


def test_registry_catalog_lists_all_forty_two_demos() -> None:
    """The catalog is the full dev fleet, present or not."""
    registry = registry_mod.ServiceRegistry()
    assert len(registry.catalog) == 42


def test_served_demos_are_exactly_the_present_ones() -> None:
    """The served list is the catalog filtered to existing demo dirs —
    the public export serves only the public examples, never "down"
    cards for absent demos."""
    registry = registry_mod.ServiceRegistry()
    present = {
        svc.slug
        for svc in registry.catalog
        if not svc.demo_dir
        or (registry_mod._DEMOS_ROOT / svc.demo_dir).is_dir()
    }
    assert {svc.slug for svc in registry.web_services()} == present
    assert len(present) >= 8  # the seven starters + storefront (public minimum)


def test_registry_includes_the_seven_starter_templates() -> None:
    registry = registry_mod.ServiceRegistry()
    starters = [s for s in registry.web_services() if s.group == "starter"]
    assert [s.slug for s in starters] == [
        "minimal-api",
        "websocket-echo",
        "auth-tokens",
        "database-tasks",
        "background-worker",
        "multi-tenant-notes",
        "ai-assistant",
    ]
    assert all(s.app_path.endswith(".app") for s in starters)


def test_registry_includes_the_three_feature_showcases() -> None:
    registry = registry_mod.ServiceRegistry()
    by_slug = {service.slug: service for service in registry.catalog}
    assert {"feature-flags", "approval-flow", "artifact-vault"} <= set(by_slug)
    assert all(
        by_slug[slug].featured
        for slug in ("feature-flags", "approval-flow", "artifact-vault")
    )


def test_registry_includes_the_events_timeline_lab() -> None:
    registry = registry_mod.ServiceRegistry()
    service = next(
        item for item in registry.catalog if item.slug == "event-timeline"
    )
    assert service.app_path == "timeline_lab.app"
    assert service.port == 8102
    assert {"event bus", "event store", "replay", "offline"} <= set(
        service.capabilities
    )


def test_registry_ports_are_unique_and_known() -> None:
    registry = registry_mod.ServiceRegistry()
    ports = [s.port for s in registry.catalog]
    assert len(set(ports)) == len(ports)
    assert 7000 not in ports  # the hub's own port


def test_every_web_demo_has_fleet_spec() -> None:
    for svc in registry_mod.ServiceRegistry().web_services():
        assert svc.demo_dir, svc.slug
        assert svc.app_path.endswith(".app"), svc.slug


def test_snapshot_reports_mounted_and_failed() -> None:
    """Snapshot reports one up and one down card among the *served* demos
    (works in dev and in the public export alike)."""
    reg = registry_mod.ServiceRegistry()
    served = [svc.slug for svc in reg.web_services()]
    assert len(served) >= 2
    up_slug, down_slug = served[0], served[-1]
    snap = reg.snapshot(
        mounted={up_slug: True},
        failures={down_slug: "Boom: x"},
    )
    by_slug = {s["slug"]: s["status"] for s in snap}
    assert by_slug[up_slug] == "up"
    assert by_slug[down_slug] == "down"


def test_rewrite_html_prefixes_assets_and_injects_shim() -> None:
    html = b'<html><head><title>t</title></head><body><a href="/x">y</a></body></html>'
    out = subsite_mod.rewrite_html(html, "/examples/rates")
    assert b'href="/examples/rates/x"' in out
    assert b'var B="/examples/rates"' in out


def test_rewrite_js_rebases_location_navigation() -> None:
    js = b'if (x) { window.location.href = "/login"; }'
    out = subsite_mod.rewrite_js(js, "/examples/auth-rbac")
    assert b'window.location.href = "/examples/auth-rbac/login"' in out


def test_rewrite_js_leaves_fetch_and_comments_alone() -> None:
    js = b'fetch("/api/keys"); // location.href = "/keep"'
    out = subsite_mod.rewrite_js(js, "/examples/x")
    assert b'fetch("/api/keys")' in out


def test_rewrite_html_leaves_external_urls() -> None:
    html = (
        b"<html><head></head><body>"
        b'<a href="https://ex.com">e</a><a href="//cdn/x">p</a>'
        b"</body></html>"
    )
    out = subsite_mod.rewrite_html(html, "/examples/rates")
    assert b'"https://ex.com"' in out
    assert b'"//cdn/x"' in out
