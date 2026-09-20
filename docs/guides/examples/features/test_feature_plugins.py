"""Feature tour: plugins with safe boot planning.

Installed plugin packages describe themselves with a `PluginDescriptor`;
before boot, `validate_plan` decides what runs: dependencies must be
satisfied, conflicts exclude both sides, and anything an admin disabled
stays off. Issues are recorded, never raised — boot is never blocked by
a bad plugin. The disabled set persists to a state file across restarts.
"""

from quadkit import load_disabled, save_disabled, update_disabled
from quadkit.contracts.plugins import PluginDescriptor
from quadkit.plugins.engine import validate_plan


def _plugin(name: str, **flags: object) -> PluginDescriptor:
    return PluginDescriptor(
        name=name,
        display_name=name.title(),
        description=f"{name} capabilities",
        icon="puzzle",
        provider_entry_point=f"{name}-pkg",
        **flags,
    )


def test_plan_enforces_dependencies_conflicts_and_disabled() -> None:
    core = _plugin("core")
    reports = _plugin("reports", requires=("core-pkg",))
    orphan = _plugin("orphan", requires=("not-installed",))
    rival = _plugin("rival", conflicts=("core-pkg",))

    plan = validate_plan([core, reports, orphan, rival], disabled=set())

    assert plan.enabled == frozenset({"core-pkg", "reports-pkg"})
    # Skips are explained, not raised.
    assert "orphan: missing dependency 'not-installed'" in plan.issues
    assert "rival: conflicts with 'core-pkg'" in plan.issues

    # Admin-disabled plugins stay out of the enabled set entirely.
    with_reports_off = validate_plan([core, reports], disabled={"reports-pkg"})
    assert with_reports_off.enabled == frozenset({"core-pkg"})
    assert with_reports_off.disabled == frozenset({"reports-pkg"})


def test_disabled_state_persists_between_restarts(tmp_path) -> None:
    state_path = tmp_path / "plugin-state.json"

    save_disabled({"clustering", "preview-feeds"}, state_path)
    assert load_disabled(state_path) == {"clustering", "preview-feeds"}

    after_remove = update_disabled(lambda names: names - {"preview-feeds"}, state_path)
    assert after_remove == {"clustering"}
    assert load_disabled(state_path) == {"clustering"}

    # Unknown/absent state file starts empty — no crash on first boot.
    assert load_disabled(tmp_path / "never-written.json") == set()
