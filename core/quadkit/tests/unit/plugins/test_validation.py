"""Tests for plugin descriptor validation and plan computation."""

from __future__ import annotations

from quadkit.contracts.plugins import PluginDescriptor
from quadkit.plugins.discovery import PluginPlan, unique_descriptors, validate_plan

_RELAY = PluginDescriptor(
    name="relay-gateway",
    display_name="AI Gateway",
    description="AI relay/gateway capabilities.",
    icon="shuffle",
    provider_entry_point="relay-gateway",
)
_RAG = PluginDescriptor(
    name="rag",
    display_name="RAG",
    description="Retrieval augmented generation.",
    icon="database",
    provider_entry_point="rag",
    requires=("relay-gateway",),
)


def test_validate_plan_enabled_and_disabled() -> None:
    plan = validate_plan([_RAG, _RELAY], disabled={"rag"})
    assert plan.enabled == {"relay-gateway"}
    assert plan.disabled == {"rag"}
    assert plan.unknown == frozenset()
    assert plan.issues == ()


def test_validate_plan_reports_unknown_disabled_entries() -> None:
    plan = validate_plan([_RELAY], disabled={"ghost", "relay-gateway"})
    assert plan.unknown == {"ghost"}


def test_validate_plan_reports_missing_dependency() -> None:
    plan = validate_plan([_RAG], disabled=set())
    assert any("missing dependency" in issue for issue in plan.issues)
    assert plan.enabled == set()


def test_validate_plan_reports_conflict() -> None:
    conflicting = PluginDescriptor(
        name="conflict",
        display_name="Conflict",
        description="conflicts with relay",
        icon="x",
        provider_entry_point="conflict",
        conflicts=("relay-gateway",),
    )
    plan = validate_plan([_RELAY, conflicting], disabled=set())
    assert any("conflicts" in issue for issue in plan.issues)


def test_deduplicates_descriptors_by_entry_point() -> None:
    dup = PluginDescriptor(
        name="dup",
        display_name="Dup",
        description="dup of relay",
        icon="copy",
        provider_entry_point="relay-gateway",
    )
    real = _RELAY
    found = unique_descriptors([real, dup])
    assert len(found) == 1
    assert found[0] is real


def test_validate_plan_returns_plan_type() -> None:
    plan = validate_plan([], set())
    assert isinstance(plan, PluginPlan)
