from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

from quadkit.cli.registry.inspect import (
    ContainerInspector,
    DependenciesInspector,
    EventsInspector,
    Inspector,
    InspectorRegistry,
    InspectionResult,
    MiddlewareInspector,
    ProvidersInspector,
    RoutesInspector,
    TasksInspector,
)


class TestInspectionResult:
    def test_success_default_data(self) -> None:
        r = InspectionResult(success=True)
        assert r.success is True
        assert r.data == {}

    def test_failure(self) -> None:
        r = InspectionResult(success=False, error="fail")
        assert r.success is False
        assert r.error == "fail"

    def test_error_default_empty_string(self) -> None:
        r = InspectionResult(success=False)
        assert r.error == ""


class TestInspector:
    def test_abc_cannot_be_instantiated(self) -> None:
        with pytest.raises(TypeError):
            Inspector()


class TestProvidersInspector:
    def test_inspect_no_config(self) -> None:
        with patch("pathlib.Path.exists", return_value=False):
            result = ProvidersInspector().inspect()
            assert result.success is False
            assert "not found" in result.error

    def test_inspect_with_config(self) -> None:
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("builtins.open", mock_open(read_data="database:\n  url: sqlite:///test.db\n")),
        ):
            result = ProvidersInspector().inspect()
            assert result.success is True
            assert "database" in result.data["providers"]

    def test_inspect_error(self) -> None:
        with (
            patch("pathlib.Path.exists", side_effect=RuntimeError("fail")),
        ):
            result = ProvidersInspector().inspect()
            assert result.success is False

    def test_name(self) -> None:
        assert ProvidersInspector().get_name() == "providers"


class TestRoutesInspector:
    def test_inspect(self) -> None:
        result = RoutesInspector().inspect()
        assert result.success is True
        assert len(result.data["routes"]) == 3

    def test_name(self) -> None:
        assert RoutesInspector().get_name() == "routes"


class TestMiddlewareInspector:
    def test_inspect(self) -> None:
        result = MiddlewareInspector().inspect()
        assert result.success is True
        assert len(result.data["middleware"]) == 3

    def test_name(self) -> None:
        assert MiddlewareInspector().get_name() == "middleware"


class TestContainerInspector:
    def test_inspect(self) -> None:
        result = ContainerInspector().inspect()
        assert result.success is True
        assert len(result.data["services"]) == 3

    def test_name(self) -> None:
        assert ContainerInspector().get_name() == "container"


class TestEventsInspector:
    def test_inspect(self) -> None:
        result = EventsInspector().inspect()
        assert result.success is True
        assert len(result.data["events"]) == 3

    def test_name(self) -> None:
        assert EventsInspector().get_name() == "events"


class TestTasksInspector:
    def test_inspect(self) -> None:
        result = TasksInspector().inspect()
        assert result.success is True
        assert len(result.data["tasks"]) == 2

    def test_name(self) -> None:
        assert TasksInspector().get_name() == "tasks"


class TestDependenciesInspector:
    def test_inspect(self) -> None:
        result = DependenciesInspector().inspect()
        assert result.success is True
        assert "AuthService" in result.data["dependencies"]

    def test_name(self) -> None:
        assert DependenciesInspector().get_name() == "dependencies"


class TestInspectorRegistry:
    def test_register_and_get(self) -> None:
        registry = InspectorRegistry()
        registry.register(ProvidersInspector)
        inspector = registry.get("providers")
        assert inspector is not None

    def test_get_nonexistent(self) -> None:
        registry = InspectorRegistry()
        assert registry.get("nonexistent") is None

    def test_get_all(self) -> None:
        registry = InspectorRegistry()
        registry.register(ProvidersInspector)
        all_ins = registry.get_all()
        assert "providers" in all_ins

    def test_get_choices(self) -> None:
        registry = InspectorRegistry.with_defaults()
        choices = registry.get_choices()
        assert "providers" in choices
        assert "routes" in choices

    def test_with_defaults_populates_all_inspectors(self) -> None:
        registry = InspectorRegistry.with_defaults()
        assert registry.get("providers") is not None
        assert registry.get("routes") is not None
