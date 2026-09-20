"""Decorator for attaching interceptors to handlers and controllers.

Mirrors :func:`~quadkit.web.security.guards.use_guards`: the router reads
``__interceptors__`` from the resolved handler (falling back to the
controller class) and executes them through ``RequestPipeline``.
"""

from __future__ import annotations

from typing import Any, TypeVar, cast

F = TypeVar("F", bound=type | Any)


def use_interceptors(*interceptors: Any) -> Any:
    """Attach one or more interceptors to a route handler or controller.

    Interceptors wrap handler execution: code before
    ``await next_handler.handle()`` runs on the way in; code after runs on
    the way out and may transform the result.  Applied to a controller
    class, the interceptors cover every route the class declares;
    handler-level interceptors take precedence.

    Args:
        *interceptors: ``WebInterceptorProtocol`` instances, attached in
            execution order.

    Example::

        @use_interceptors(EnvelopeInterceptor())
        class ReportsController(Controller): ...

        @use_interceptors(AuditLogInterceptor())
        async def sensitive_action(self): ...
    """

    def decorator(target: F) -> F:
        instances = [
            interceptor() if isinstance(interceptor, type) else interceptor
            for interceptor in interceptors
        ]
        existing = list(getattr(target, "__interceptors__", []) or [])
        cast("Any", target).__interceptors__ = existing + instances
        return target

    return decorator
