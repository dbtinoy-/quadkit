"""Tests for RouteRegistry and ControllerRegistry synchronization.

Ensures that when a controller is registered via RouteRegistry.register_controller(),
it is also registered in ControllerRegistry atomically, preventing inconsistencies.
"""

from __future__ import annotations

import pytest

from quadkit.web.routing.controller_registry import ControllerRegistry
from quadkit.web.routing.controllers import Controller
from quadkit.web.routing.registry import RouteRegistry


class TestRegistrySync:
    """Test atomic synchronization between RouteRegistry and ControllerRegistry."""

    def test_register_controller_syncs_to_controller_registry(self) -> None:
        """Registering in RouteRegistry also appears in ControllerRegistry."""
        routes = RouteRegistry()
        controllers = ControllerRegistry()

        class PetController(Controller):
            pass

        # Pass controller_registry so sync happens
        routes.register_controller(
            PetController,
            controller_registry=controllers,
        )

        # Should now be in controller registry too
        result = controllers.get("PetController")
        assert result is PetController

    def test_register_controller_without_controller_registry_still_works(self) -> None:
        """register_controller() without controller_registry kwarg still works (backward compat)."""
        routes = RouteRegistry()

        class UserController(Controller):
            pass

        # Should NOT raise when controller_registry not passed
        routes.register_controller(UserController)
        # Verify it's at least in the routes registry
        assert UserController in routes.get_controllers()

    def test_both_registries_have_same_controller_after_sync(self) -> None:
        """After sync, both registries return the same class."""
        routes = RouteRegistry()
        controllers = ControllerRegistry()

        class OrderController(Controller):
            pass

        routes.register_controller(
            OrderController,
            controller_registry=controllers,
        )

        # Verify it's in both
        from_route_registry = routes.get_controllers()
        from_controller_registry = controllers.get("OrderController")
        assert OrderController in from_route_registry
        assert from_controller_registry is OrderController

    def test_multiple_controllers_sync_atomically(self) -> None:
        """Multiple controllers register and sync independently."""
        routes = RouteRegistry()
        controllers = ControllerRegistry()

        class Controller1(Controller):
            pass

        class Controller2(Controller):
            pass

        class Controller3(Controller):
            pass

        # Register each one
        routes.register_controller(Controller1, controller_registry=controllers)
        routes.register_controller(Controller2, controller_registry=controllers)
        routes.register_controller(Controller3, controller_registry=controllers)

        # All should be in both registries
        assert controllers.get("Controller1") is Controller1
        assert controllers.get("Controller2") is Controller2
        assert controllers.get("Controller3") is Controller3
        assert len(routes.get_controllers()) == 3

    def test_sync_preserves_controller_by_name(self) -> None:
        """Synced controller is stored by class name in ControllerRegistry."""
        routes = RouteRegistry()
        controllers = ControllerRegistry()

        class ArticleController(Controller):
            pass

        routes.register_controller(
            ArticleController,
            controller_registry=controllers,
        )

        # Lookup should use the class name
        assert controllers.get("ArticleController") is ArticleController
        assert "ArticleController" in controllers.list_controllers()

    def test_controller_registry_none_does_not_raise(self) -> None:
        """Explicitly passing controller_registry=None is safe."""
        routes = RouteRegistry()

        class SafeController(Controller):
            pass

        # Should not raise
        routes.register_controller(
            SafeController,
            controller_registry=None,
        )
        # Should still be in routes registry
        assert SafeController in routes.get_controllers()

    def test_sync_idempotent_no_duplicates(self) -> None:
        """Registering the same controller twice doesn't create duplicates."""
        routes = RouteRegistry()
        controllers = ControllerRegistry()

        class IdempotentController(Controller):
            pass

        # Register twice
        routes.register_controller(
            IdempotentController,
            controller_registry=controllers,
        )
        routes.register_controller(
            IdempotentController,
            controller_registry=controllers,
        )

        # Should have only one instance in each registry
        assert routes.get_controllers().count(IdempotentController) == 1
        assert controllers.get("IdempotentController") is IdempotentController
