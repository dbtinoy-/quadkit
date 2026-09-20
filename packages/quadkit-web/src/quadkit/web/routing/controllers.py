"""Controller base class with DI support"""

from __future__ import annotations

from typing import Any


class Controller:
    """Base controller class with dependency injection support.

    Controllers group related route handlers and can specify dependencies
    to be injected by the DI container.

    Example:
        class UserController(Controller):
            @get("/users")
            async def list_users(self):
                return []
    """

    def __init__(self) -> None:
        # Dependencies will be injected by DI container
        pass

    @classmethod
    def collect_routes(cls) -> list[dict[str, Any]]:
        """Collect routes from controller methods.

        It scans the class and its base classes for methods with
        _route_config attribute and returns a list of route definitions.

        Returns:
            List of route dictionaries with keys: method, path, handler_name, etc.
        """
        routes = []
        seen_handlers = set()

        # Collect from MRO (Method Resolution Order) - base classes first
        for klass in cls.__mro__:
            if klass is Controller or klass is object:
                continue

            for attr_name in dir(klass):
                if attr_name.startswith("_") or attr_name in seen_handlers:
                    continue

                attr_value = getattr(klass, attr_name, None)
                if attr_value is not None and hasattr(attr_value, "_route_config"):
                    route_config = attr_value._route_config
                    routes.append(
                        {
                            "method": route_config["method"],
                            "path": route_config["path"],
                            "handler_name": attr_name,
                            "response_model": route_config.get("response_model"),
                            "request_model": route_config.get("request_model"),
                            "status_code": route_config.get("status_code", 200),
                            "summary": route_config.get("summary"),
                            "description": route_config.get("description"),
                            "tags": route_config.get("tags"),
                            "operation_id": route_config.get("operation_id"),
                            "responses": route_config.get("responses"),
                            "deprecated": route_config.get("deprecated", False),
                        },
                    )
                    seen_handlers.add(attr_name)

        return routes
