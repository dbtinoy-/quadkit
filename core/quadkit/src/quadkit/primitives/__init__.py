"""Quadkit Core — Core framework primitives: builders, contexts, registries.

This module uses lazy imports for all public symbols to keep
import overhead minimal.  Every name listed in _LAZY_IMPORTS
is available at package level:

    from quadkit.primitives import <Symbol>

or by accessing the attribute on the package:

    import quadkit.primitives as core
    core.<Symbol>
"""

from __future__ import annotations

__path__ = __import__("pkgutil").extend_path(__path__, __name__)

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from quadkit.primitives.builder import (
        AbstractBuilder,
        buildable,
        builder_field,
    )
    from quadkit.primitives.context import (
        CAUSATION_ID,
        CORRELATION_ID,
        DEFAULT_KEYS,
        REQUEST_ID,
        REQUEST_METHOD,
        REQUEST_PATH,
        REQUEST_START_TIME,
        SPAN_ID,
        TENANT_ID,
        TRACE_FLAGS,
        TRACE_ID,
        USER_ID,
        Context,
        ContextKey,
        ContextVarRegistry,
        RequestContext,
        create_context_registry,
        create_default_context,
        get_request_context,
        propagate_context,
        request_scope,
        with_context,
    )
    from quadkit.primitives.pipeline import (
        PipelineContext,
        PipelineStep,
    )
    from quadkit.primitives.registry import (
        Registry,
        RegistryIntrospector,
        entry_point_catalog,
        on_register,
        on_unregister,
        registry_info,
    )
    from quadkit.primitives.trusted_html import (
        TrustedHTML,
        escape_json_for_html,
        json_for_html,
        trusted_html,
        trusted_static_script,
        trusted_svg_icon,
        trusted_template_output,
    )

_LAZY_IMPORTS: dict[str, str] = {
    "AbstractBuilder": "quadkit.primitives.builder",
    "buildable": "quadkit.primitives.builder",
    "builder_field": "quadkit.primitives.builder",
    # context — keys
    "CAUSATION_ID": "quadkit.primitives.context",
    "CORRELATION_ID": "quadkit.primitives.context",
    "DEFAULT_KEYS": "quadkit.primitives.context",
    "REQUEST_ID": "quadkit.primitives.context",
    "REQUEST_METHOD": "quadkit.primitives.context",
    "REQUEST_PATH": "quadkit.primitives.context",
    "REQUEST_START_TIME": "quadkit.primitives.context",
    "SPAN_ID": "quadkit.primitives.context",
    "TENANT_ID": "quadkit.primitives.context",
    "TRACE_FLAGS": "quadkit.primitives.context",
    "TRACE_ID": "quadkit.primitives.context",
    "USER_ID": "quadkit.primitives.context",
    # clock
    "clock": "quadkit.primitives.clock",
    # context — classes
    "Context": "quadkit.primitives.context",
    "ContextKey": "quadkit.primitives.context",
    "ContextVarRegistry": "quadkit.primitives.context",
    "RequestContext": "quadkit.primitives.context",
    # context — factories & helpers
    "create_context_registry": "quadkit.primitives.context",
    "create_default_context": "quadkit.primitives.context",
    "get_request_context": "quadkit.primitives.context",
    "propagate_context": "quadkit.primitives.context",
    "request_scope": "quadkit.primitives.context",
    "with_context": "quadkit.primitives.context",
    # registry
    "Registry": "quadkit.primitives.registry",
    "on_register": "quadkit.primitives.registry",
    "on_unregister": "quadkit.primitives.registry",
    # registry introspection
    "RegistryIntrospector": "quadkit.primitives.registry.introspection",
    "entry_point_catalog": "quadkit.primitives.registry.introspection",
    "registry_info": "quadkit.primitives.registry.introspection",
    # exceptions
    "CoreError": "quadkit.primitives.exceptions",
    # constants
    "REQUEST_ID_KEY": "quadkit.primitives.constants",
    "TENANT_ID_KEY": "quadkit.primitives.constants",
    "TRACE_ID_KEY": "quadkit.primitives.constants",
    "SPAN_ID_KEY": "quadkit.primitives.constants",
    "USER_ID_KEY": "quadkit.primitives.constants",
    "REQUEST_PATH_KEY": "quadkit.primitives.constants",
    "REQUEST_METHOD_KEY": "quadkit.primitives.constants",
    "REQUEST_START_TIME_KEY": "quadkit.primitives.constants",
    # types
    "Priority": "quadkit.primitives.types",
    # protocols
    "Buildable": "quadkit.primitives.protocols",
    "Registrable": "quadkit.primitives.protocols",
    # pipeline
    "PipelineContext": "quadkit.primitives.pipeline",
    "PipelineStep": "quadkit.primitives.pipeline",
    "LazyImport": "quadkit.primitives.lazy",
    # trusted HTML — the render-trust boundary
    "TrustedHTML": "quadkit.primitives.trusted_html",
    "escape_json_for_html": "quadkit.primitives.trusted_html",
    "json_for_html": "quadkit.primitives.trusted_html",
    "trusted_html": "quadkit.primitives.trusted_html",
    "trusted_static_script": "quadkit.primitives.trusted_html",
    "trusted_svg_icon": "quadkit.primitives.trusted_html",
    "trusted_template_output": "quadkit.primitives.trusted_html",
}


def __getattr__(name: str) -> Any:
    if name in _LAZY_IMPORTS:
        import importlib

        module = importlib.import_module(_LAZY_IMPORTS[name])
        value = getattr(module, name)
        globals()[name] = value
        return value
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)


def __dir__() -> list[str]:
    return list(_LAZY_IMPORTS.keys())


__all__ = list(_LAZY_IMPORTS.keys())
__version__ = "0.1.0"
