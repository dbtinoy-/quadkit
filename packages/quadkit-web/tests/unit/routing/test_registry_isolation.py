"""Tests for route and controller registry isolation and DI integration."""

from __future__ import annotations

from quadkit.web.filters.pipeline import FilterPipeline, filter_pipeline
from quadkit.web.routing.controller_registry import (
    ControllerRegistry,
    controller_registry,
)
from quadkit.web.routing.controllers import Controller
from quadkit.web.routing.registry import RouteRegistry, route_registry


class TestRouteRegistryIsolation:
    """Test RouteRegistry clear() method for test isolation."""

    def test_get_route_registry_returns_same_instance(self) -> None:
        """Verify the module-level instance is the global singleton."""
        from quadkit.web.routing.registry import get_route_registry

        r1 = get_route_registry()
        r2 = get_route_registry()
        assert r1 is r2
        assert r1 is route_registry

    def test_route_registry_instances_are_independent(self) -> None:
        """Verify fresh instances are independent."""
        r1 = RouteRegistry()
        r2 = RouteRegistry()
        assert r1 is not r2

    def test_route_registry_clear_removes_all_routes(self) -> None:
        """Verify clear() empties the route registry."""
        registry = RouteRegistry()

        # Register a fake route
        registry._items["/test"] = {"GET": {"handler": "test_handler"}}
        assert len(registry._items) > 0

        # Clear
        registry.clear()

        # Verify empty
        assert len(registry._items) == 0

    def test_route_registry_clear_removes_all_controllers(self) -> None:
        """Verify clear() empties the controller list."""

        class FakeController(Controller):
            pass

        registry = RouteRegistry()
        registry.register_controller(FakeController)
        assert len(registry._controllers) == 1

        # Clear
        registry.clear()

        # Verify empty
        assert len(registry._controllers) == 0

    def test_global_route_registry_can_be_cleared(self) -> None:
        """Verify the global instance can be cleared."""
        # Add a route to the global registry
        route_registry._items["/global/test"] = {"GET": {"handler": "test"}}
        assert len(route_registry._items) > 0

        # Clear
        route_registry.clear()

        # Verify empty
        assert len(route_registry._items) == 0


class TestControllerRegistryIsolation:
    """Test ControllerRegistry clear() method for test isolation."""

    def test_controller_registry_register_and_get(self) -> None:
        """Verify basic register/get functionality."""

        class MyController:
            pass

        registry = ControllerRegistry()
        registry.register("MyController", MyController)
        assert registry.get("MyController") is MyController

    def test_controller_registry_clear_removes_all(self) -> None:
        """Verify clear() empties all controller registrations."""

        class Controller1:
            pass

        class Controller2:
            pass

        registry = ControllerRegistry()
        registry.register("Controller1", Controller1)
        registry.register("Controller2", Controller2)
        assert len(registry.list_controllers()) == 2

        # Clear
        registry.clear()

        # Verify empty
        assert len(registry.list_controllers()) == 0

    def test_global_controller_registry_can_be_cleared(self) -> None:
        """Verify the global instance can be cleared."""

        class GlobalController:
            pass

        controller_registry.register("GlobalController", GlobalController)
        initial_count = len(controller_registry.list_controllers())
        assert initial_count >= 1

        # Clear
        controller_registry.clear()

        # Verify empty
        assert len(controller_registry.list_controllers()) == 0


class TestFilterPipelineIsolation:
    """Test FilterPipeline clear() method for test isolation."""

    def test_filter_pipeline_has_clear_method(self) -> None:
        """Verify FilterPipeline has a clear() method."""
        pipeline = FilterPipeline()
        assert hasattr(pipeline, "clear")
        assert callable(pipeline.clear)

    def test_filter_pipeline_clear_removes_all_filters(self) -> None:
        """Verify clear() empties all filters."""
        from unittest.mock import MagicMock

        pipeline = FilterPipeline()

        # Add mock filters
        mock_filter1 = MagicMock()
        mock_filter1.can_handle = MagicMock(return_value=False)
        mock_filter2 = MagicMock()
        mock_filter2.can_handle = MagicMock(return_value=False)

        pipeline.add_filter(mock_filter1)
        pipeline.add_filter(mock_filter2)
        assert len(pipeline.filters) == 2

        # Clear
        pipeline.clear()

        # Verify empty
        assert len(pipeline.filters) == 0

    def test_global_filter_pipeline_can_be_cleared(self) -> None:
        """Verify the global instance can be cleared."""
        from unittest.mock import MagicMock

        # Add a mock filter
        mock_filter = MagicMock()
        mock_filter.can_handle = MagicMock(return_value=False)
        filter_pipeline.add_filter(mock_filter)
        assert len(filter_pipeline.filters) >= 1

        # Clear
        filter_pipeline.clear()

        # Verify empty
        assert len(filter_pipeline.filters) == 0


class TestConfTestFixtureIntegration:
    """Test that conftest.py autouse fixture resets registries."""

    def test_route_registry_empty_at_test_start(self) -> None:
        """Verify route registry is clean at test start (via conftest autouse)."""
        # This test runs after the autouse fixture, so should be clean.
        # We add a route to verify the fixture cleaned up after the previous test.
        assert len(route_registry._items) == 0

    def test_controller_registry_empty_at_test_start(self) -> None:
        """Verify controller registry is clean at test start (via conftest autouse)."""
        assert len(controller_registry.list_controllers()) == 0

    def test_filter_pipeline_empty_at_test_start(self) -> None:
        """Verify filter pipeline is clean at test start (via conftest autouse)."""
        assert len(filter_pipeline.filters) == 0
