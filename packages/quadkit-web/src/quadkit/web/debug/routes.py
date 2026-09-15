"""Debug routes for development.

Provides /debug/routes and /debug/di-graph endpoints.
"""

from __future__ import annotations

from typing import Any

from quadkit.web.exceptions import ForbiddenError


async def _check_admin(request: Any) -> None:
    """Ensure the current user is an admin."""
    user = request.scope.get("extensions", {}).get("user")
    if not user:
        raise ForbiddenError("Authentication required")

    role = user.get("role")
    roles = user.get("roles", [])
    if role != "admin" and "admin" not in roles:
        raise ForbiddenError("Admin access required")


async def debug_routes(request: Any) -> Any:
    """List all registered routes in a table format."""
    await _check_admin(request)
    from starlette.responses import JSONResponse

    # Get routes from the app
    routes = []

    if hasattr(request.app, "routes"):
        for route in request.app.routes:
            route_info = {
                "path": getattr(route, "path", "/"),
                "methods": getattr(route, "methods", []),
            }

            # Get handler info
            if hasattr(route, "endpoint"):
                endpoint = route.endpoint
                route_info["handler"] = getattr(endpoint, "__name__", str(endpoint))
                route_info["module"] = getattr(endpoint, "__module__", "")

            routes.append(route_info)

    return JSONResponse(
        {
            "routes": routes,
            "count": len(routes),
        },
    )


async def debug_di_graph(request: Any) -> Any:
    """Generate a DI dependency graph in DOT/Mermaid format."""
    await _check_admin(request)
    from starlette.responses import JSONResponse

    format = request.query_params.get("format", "json")

    # Try to get container from app state
    container = None
    if hasattr(request.app, "state"):
        container = getattr(request.app.state, "container", None)

    if not container:
        return JSONResponse(
            {"error": "Container not available"},
            status_code=404,
        )

    # Build dependency graph
    graph: dict[str, list[Any]] = {
        "nodes": [],
        "edges": [],
    }

    if hasattr(container, "_registry"):
        for descriptor in container._registry.all():
            service_name = getattr(
                descriptor.service_type,
                "__name__",
                str(descriptor.service_type),
            )
            node = {
                "id": service_name,
                "name": service_name,
                "lifetime": descriptor.scope.value
                if hasattr(descriptor.scope, "value")
                else str(descriptor.scope),
            }
            graph["nodes"].append(node)

    if format == "mermaid":
        # Generate Mermaid graph
        lines = ["graph LR"]
        for node in graph["nodes"]:
            lifetime = node.get("lifetime", "")
            lines.append(f'    {node["id"]}["{node["name"]} ({lifetime})"]')

        output = "\n".join(lines)
        return JSONResponse({"mermaid": output})

    return JSONResponse(graph)


async def debug_container(request: Any) -> Any:
    """List all registered services in the DI container."""
    await _check_admin(request)
    from starlette.responses import JSONResponse

    container = None
    if hasattr(request.app, "state"):
        container = getattr(request.app.state, "container", None)

    if not container:
        return JSONResponse(
            {"error": "Container not available"},
            status_code=404,
        )

    services = []

    if hasattr(container, "_registry"):
        for descriptor in container._registry.all():
            services.append(
                {
                    "name": getattr(
                        descriptor.service_type,
                        "__name__",
                        str(descriptor.service_type),
                    ),
                    "lifetime": descriptor.scope.value
                    if hasattr(descriptor.scope, "value")
                    else str(descriptor.scope),
                    "type": str(descriptor.implementation),
                },
            )

    return JSONResponse(
        {
            "services": services,
            "count": len(services),
        },
    )
