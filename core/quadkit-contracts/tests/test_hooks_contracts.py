"""Tests for HookPriority and HookRegistryProtocol contracts."""
from __future__ import annotations

from quadkit.contracts.core.hooks import HookPriority, HookRegistryProtocol


class TestHookPriority:
    def test_priority_ordering(self) -> None:
        assert HookPriority.EARLIEST < HookPriority.EARLY
        assert HookPriority.EARLY < HookPriority.NORMAL
        assert HookPriority.NORMAL < HookPriority.LATE
        assert HookPriority.LATE < HookPriority.LATEST

    def test_priority_is_int(self) -> None:
        assert isinstance(HookPriority.NORMAL, int)

    def test_priority_values(self) -> None:
        assert HookPriority.EARLIEST == 0
        assert HookPriority.EARLY == 50
        assert HookPriority.NORMAL == 100
        assert HookPriority.LATE == 200
        assert HookPriority.LATEST == 300

    def test_custom_int_comparison(self) -> None:
        assert HookPriority.EARLY + 10 < HookPriority.NORMAL


class TestHookRegistryProtocol:
    def test_protocol_is_runtime_checkable(self) -> None:
        from unittest.mock import AsyncMock, MagicMock

        class MinimalRegistry:
            register_action = MagicMock()
            register_filter = MagicMock()
            unregister_action = MagicMock()
            unregister_filter = MagicMock()
            call_action = AsyncMock()
            apply_filter = AsyncMock()
            has_action = MagicMock()
            has_filter = MagicMock()
            clear = MagicMock()

        assert isinstance(MinimalRegistry(), HookRegistryProtocol)

    def test_exported_from_contracts_core(self) -> None:
        from quadkit.contracts import core
        assert core.HookPriority is HookPriority
        assert core.HookRegistryProtocol is HookRegistryProtocol

    def test_non_compliant_class_fails_protocol_check(self) -> None:
        """A class missing protocol methods must not satisfy isinstance()."""
        class NotARegistry:
            def register_action(self, hook_name: str, handler: object) -> None: ...

        assert not isinstance(NotARegistry(), HookRegistryProtocol)
