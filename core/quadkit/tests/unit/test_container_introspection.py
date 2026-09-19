"""Tests for ContainerIntrospectionMixin (validation + diagnostics surface)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from quadkit.di.container.container_introspection import ContainerIntrospectionMixin
from quadkit.di.container.validation import OrphanedRegistration


class _Introspectable(ContainerIntrospectionMixin):
    """Minimal host carrying the mixin's collaborators."""

    def __init__(self) -> None:
        self._validator = MagicMock()
        self._diagnostics = MagicMock()
        self._registry = MagicMock()
        self._parent = None


def _reg(service_type: type) -> Any:
    d = MagicMock()
    d.service_type = service_type
    return d


class _SvcA:
    pass


class _SvcB:
    pass


class TestValidate:
    def test_delegates_to_validator(self) -> None:
        host = _Introspectable()
        host._validator.validate.return_value = ["issue-1", "issue-2"]
        assert host.validate() == ["issue-1", "issue-2"]
        host._validator.validate.assert_called_once()

    def test_empty_when_valid(self) -> None:
        host = _Introspectable()
        host._validator.validate.return_value = []
        assert host.validate() == []


class TestOrphans:
    def test_delegates_to_validator(self) -> None:
        host = _Introspectable()
        orphan = OrphanedRegistration(service_key="_SvcA", registered_at="2026-01-01", suggestion="remove")
        host._validator.validate_no_orphans.return_value = [orphan]
        result = host.validate_no_orphans()
        assert result == [orphan]
        host._validator.validate_no_orphans.assert_called_once()


class TestRegisteredServices:
    def test_lists_registered_service_names(self) -> None:
        host = _Introspectable()
        host._registry.all.return_value = [_reg(_SvcA), _reg(_SvcB)]
        assert host._registered_services() == ["_SvcA", "_SvcB"]

    def test_parent_services_included(self) -> None:
        parent = _Introspectable()
        parent._registry.all.return_value = [_reg(_SvcA)]
        child = _Introspectable()
        child._parent = parent
        child._registry.all.return_value = [_reg(_SvcB)]
        assert child._registered_services() == ["_SvcA", "_SvcB"]

    def test_non_type_service_uses_str(self) -> None:
        host = _Introspectable()
        d = MagicMock()
        d.service_type = "not-a-type"
        host._registry.all.return_value = [d]
        assert host._registered_services() == ["not-a-type"]


class TestDiagnostics:
    def test_dump_registrations_delegates(self) -> None:
        host = _Introspectable()
        host._diagnostics.dump_registrations.return_value = [{"type": "_SvcA"}]
        assert host.dump_registrations() == [{"type": "_SvcA"}]
        host._diagnostics.dump_registrations.assert_called_once()

    def test_dump_dependency_graph_delegates(self) -> None:
        host = _Introspectable()
        host._diagnostics.dump_dependency_graph.return_value = {"_SvcA": ["_SvcB"]}
        assert host.dump_dependency_graph() == {"_SvcA": ["_SvcB"]}

    def test_log_registrations_delegates(self) -> None:
        host = _Introspectable()
        host.log_registrations()
        host._diagnostics.log_registrations.assert_called_once()
