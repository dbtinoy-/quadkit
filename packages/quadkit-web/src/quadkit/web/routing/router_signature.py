"""Handler signature analysis for the router.

Registration-time introspection: a controller method's signature and resolved
type hints are computed once and cached, together with the zero-binding fast
path (plans/09172026 R-05) that lets request-time parameter binding be skipped
for handlers whose parameters are all request/context injections.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import lru_cache
import inspect
from typing import TYPE_CHECKING, Any, get_origin, get_type_hints

from quadkit.logging import get_logger

logger = get_logger(__name__)


@lru_cache(maxsize=1024)
def _cached_get_type_hints(func: Callable[..., Any]) -> Any:
    """Cached wrapper around typing.get_type_hints(func, globalns=func.__globals__).

    - Caching avoids repeatedly resolving forward refs at request time.
    - Keyed by function object so it's invalidated when the function object is GC'd.
    - Follows __wrapped__ chain to get the original function's __globals__,
      which is necessary when decorators use @functools.wraps and the handler
      has `from __future__ import annotations`.
    """
    target = func
    while hasattr(target, "__wrapped__"):
        target = target.__wrapped__

    globalns = getattr(target, "__globals__", None) or getattr(func, "__globals__", {})
    try:
        return get_type_hints(func, globalns=globalns) or {}
    except (NameError, AttributeError, TypeError):
        try:
            return get_type_hints(target) or {}
        except (NameError, AttributeError, TypeError):
            return {}


class RouterSignatureMixin:
    """Handler signature and fast-path binding analysis."""

    if TYPE_CHECKING:
        # Collaborators provided by Router on composition.
        _signature_cache: dict[tuple[type, str], dict[str, Any]]

    def _get_handler_signature(
        self,
        controller_cls: type,
        method_name: str,
    ) -> dict[str, Any]:
        """Get cached handler signature or compute and cache it.

        Args:
            controller_cls: The controller class.
            method_name: The method name.

        Returns:
            Dict with 'sig', 'hints', and computed params.
        """
        cache_key = (controller_cls, method_name)
        if cache_key in self._signature_cache:
            return self._signature_cache[cache_key]

        handler = getattr(controller_cls, method_name)
        sig = inspect.signature(handler)

        # Resolve string annotations (cached)
        try:
            hints = _cached_get_type_hints(handler)
        except (NameError, AttributeError, TypeError) as e:
            hints = {}
            logger.debug(
                "Failed to resolve type hints for %s.%s: %s",
                controller_cls.__name__,
                method_name,
                e,
            )

        # Compute DI params info at registration time
        di_params = {}
        body_param = None

        for param_name, param in sig.parameters.items():
            if param_name in ("self", "cls"):
                continue
            if param.annotation is inspect.Parameter.empty:
                continue

            # Determine if this is a DI-injectable param
            origin = get_origin(param.annotation)
            if origin is not None:
                di_params[param_name] = param.annotation

        result = {
            "sig": sig,
            "hints": hints,
            "di_params": di_params,
            "body_param": body_param,
        }

        self._signature_cache[cache_key] = result
        return result

    def _compute_simple_binding(
        self,
        controller_cls: type,
        method_name: str,
    ) -> dict[str, str] | None:
        """Precompute the parameter-binding fast path (plans/09172026 R-05).

        Returns a ``{param_name: "request" | "context"}`` plan when every
        handler parameter (besides ``self``) is a request or execution-context
        injection — the signature shapes for which full parameter binding and
        request validation are provably no-ops. Returns ``None`` for any other
        signature so the general binder path stays untouched.

        Computed once at route-wrap time, not per request.
        """
        try:
            sig_info = self._get_handler_signature(controller_cls, method_name)
        except Exception:  # noqa: BLE001 — fast path is best-effort; the binder handles the rest
            return None

        sig = sig_info["sig"]
        hints = sig_info.get("hints") or {}

        from quadkit.web.protocols import ExecutionContextProtocol
        from quadkit.web.routing.execution_context import WebExecutionContext
        from quadkit.web.routing.parameter_binder import ParameterBinder

        binder = ParameterBinder(sig, hints)
        plan: dict[str, str] = {}
        for name, param in sig.parameters.items():
            if name == "self":
                continue
            annotation = hints.get(name, param.annotation)
            if annotation in (WebExecutionContext, ExecutionContextProtocol):
                plan[name] = "context"
                continue
            if binder._is_request_type(annotation, name):  # noqa: SLF001 — reuse of the binder's own request-detection
                plan[name] = "request"
                continue
            # Any other parameter (path/query/body/DI/default) needs the
            # full binder: it may bind from the request or the container.
            return None
        return plan
