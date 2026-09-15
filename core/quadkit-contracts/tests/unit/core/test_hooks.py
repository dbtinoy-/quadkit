"""Tests for hooks protocols."""

from __future__ import annotations

from quadkit.contracts.core.hooks import HookPriority, HookRegistryProtocol


class TestHookPriority:
    """Tests for HookPriority enum."""

    def test_all_priorities(self) -> None:
        assert HookPriority.EARLIEST == 0
        assert HookPriority.EARLY == 50
        assert HookPriority.NORMAL == 100
        assert HookPriority.LATE == 200
        assert HookPriority.LATEST == 300

    def test_is_int_enum(self) -> None:
        priority = HookPriority.NORMAL
        assert isinstance(priority, int)
        assert priority == 100


class TestHookRegistryProtocol:
    """Tests for HookRegistryProtocol."""

    def test_has_register_action_method(self) -> None:
        assert hasattr(HookRegistryProtocol, "register_action")

    def test_has_register_filter_method(self) -> None:
        assert hasattr(HookRegistryProtocol, "register_filter")

    def test_has_unregister_action_method(self) -> None:
        assert hasattr(HookRegistryProtocol, "unregister_action")

    def test_has_unregister_filter_method(self) -> None:
        assert hasattr(HookRegistryProtocol, "unregister_filter")

    def test_has_call_action_method(self) -> None:
        assert hasattr(HookRegistryProtocol, "call_action")

    def test_has_apply_filter_method(self) -> None:
        assert hasattr(HookRegistryProtocol, "apply_filter")

    def test_has_has_action_method(self) -> None:
        assert hasattr(HookRegistryProtocol, "has_action")

    def test_has_has_filter_method(self) -> None:
        assert hasattr(HookRegistryProtocol, "has_filter")

    def test_has_clear_method(self) -> None:
        assert hasattr(HookRegistryProtocol, "clear")