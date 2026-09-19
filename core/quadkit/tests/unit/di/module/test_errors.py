# file: tests/di/module/test_errors.py
"""Tests for diagnostic error message quality."""

from __future__ import annotations

import pytest

from quadkit.di.module.errors import (
    format_cycle_error,
    format_duplicate_module_error,
    format_missing_export_error,
    format_missing_import_error,
    format_not_a_module_error,
    format_visibility_error,
)


class TestCycleErrorFormat:
    def test_contains_cycle_path(self):
        msg = format_cycle_error(["A", "B", "C", "A"])
        assert "A → B → C → A" in msg

    def test_contains_fix_suggestion(self):
        msg = format_cycle_error(["X", "Y", "X"])
        assert "Break the cycle" in msg
        assert "Extract shared types" in msg


class TestMissingImportErrorFormat:
    def test_names_module_and_missing(self):
        msg = format_missing_import_error("Billing", "Payment", ["Auth", "Billing"])
        assert "Billing imports 'Payment'" in msg
        assert "Payment is not registered" in msg

    def test_lists_available_modules(self):
        msg = format_missing_import_error("X", "Y", ["A", "B", "C"])
        assert "A" in msg
        assert "B" in msg
        assert "C" in msg

    def test_contains_fix_suggestion(self):
        msg = format_missing_import_error("X", "Y", [])
        assert "To fix:" in msg
        assert "add_module" in msg


class TestMissingExportErrorFormat:
    def test_names_module_and_export(self):
        msg = format_missing_export_error(
            "Cache", "CacheBackendProtocol", ["CacheProvider"], ["CacheKey"],
        )
        assert "Cache declares export 'CacheBackendProtocol'" in msg
        assert "no provider in Cache registered" in msg

    def test_lists_providers_and_registered(self):
        msg = format_missing_export_error(
            "M", "X", ["ProvA", "ProvB"], ["TypeY", "TypeZ"],
        )
        assert "ProvA" in msg
        assert "ProvB" in msg
        assert "TypeY" in msg
        assert "TypeZ" in msg

    def test_contains_fix_suggestion(self):
        msg = format_missing_export_error("M", "X", [], [])
        assert "To fix:" in msg


class TestVisibilityErrorFormat:
    def test_names_all_parties(self):
        msg = format_visibility_error(
            "Billing", "BillingProvider", "Auth", "TokenService", ["AuthProto"],
        )
        assert "BillingProvider" in msg
        assert "Billing" in msg or "BillingModule" in msg
        assert "TokenService" in msg
        assert "Auth" in msg

    def test_lists_exported_types(self):
        msg = format_visibility_error(
            "A", "AProv", "B", "Secret", ["PublicB", "OtherB"],
        )
        assert "PublicB" in msg
        assert "OtherB" in msg

    def test_contains_fix_suggestion(self):
        msg = format_visibility_error("A", "AP", "B", "S", [])
        assert "To fix:" in msg


class TestDuplicateModuleErrorFormat:
    def test_names_module(self):
        msg = format_duplicate_module_error("DbModule", "first call", "second call")
        assert "DbModule" in msg
        assert "first call" in msg
        assert "second call" in msg

    def test_contains_fix_suggestion(self):
        msg = format_duplicate_module_error("X", "a", "b")
        assert "To fix:" in msg
        assert "configured once" in msg


class TestNotAModuleErrorFormat:
    def test_names_entry(self):
        msg = format_not_a_module_error("MyClass", "str")
        assert "MyClass" in msg
        assert "not a valid module" in msg

    def test_contains_example(self):
        msg = format_not_a_module_error("Foo", "int")
        assert "@module" in msg
        assert "DynamicModule" in msg
