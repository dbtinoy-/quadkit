"""Provider and module exception classes."""

from __future__ import annotations

from typing import Any

from quadkit.contracts.exceptions.base import QuadkitError


class ProviderError(QuadkitError):
    """Provider configuration or lifecycle error."""

    _code = "QK_ERR_PROV_001"

    def __init__(self, message: str = "Provider error", **kwargs: Any) -> None:
        super().__init__(message=message, **kwargs)


class ModuleError(QuadkitError):
    """Module configuration or lifecycle error."""

    _code = "QK_ERR_MOD_001"

    def __init__(self, message: str = "Module error", **kwargs: Any) -> None:
        super().__init__(message=message, **kwargs)


class ModuleImportError(ModuleError):
    """A module imports a module that does not exist in the graph.

    Raised during module compilation when a module's ``imports``
    references a module class that is not registered in the
    application's module graph.
    """

    _code = "QK_ERR_MOD_002"

    def __init__(
        self,
        message: str = "Module import not found",
        *,
        module_name: str | None = None,
        missing_import: str | None = None,
        available_modules: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        details = kwargs.pop("details", {})
        if module_name:
            details["module"] = module_name
        if missing_import:
            details["missing_import"] = missing_import
        if available_modules:
            details["available_modules"] = available_modules
        super().__init__(
            message=message,
            details=details,
            **kwargs,
        )


class ModuleExportError(ModuleError):
    """A module exports a type not provided by its providers.

    Raised during post-registration validation when a module
    declares an export that no provider in that module actually
    registered in the container.
    """

    _code = "QK_ERR_MOD_003"

    def __init__(
        self,
        message: str = "Module export not registered",
        *,
        module_name: str | None = None,
        missing_export: str | None = None,
        registered_types: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        details = kwargs.pop("details", {})
        if module_name:
            details["module"] = module_name
        if missing_export:
            details["missing_export"] = missing_export
        if registered_types:
            details["registered_types"] = registered_types
        super().__init__(
            message=message,
            details=details,
            **kwargs,
        )


class ModuleCycleError(ModuleError):
    """Circular dependency detected in the module import graph.

    Raised during module compilation when a cycle is detected in
    the module import graph, e.g. ``A → B → C → A``.
    """

    _code = "QK_ERR_MOD_004"

    def __init__(
        self,
        message: str = "Circular module dependency detected",
        *,
        cycle: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        details = kwargs.pop("details", {})
        if cycle:
            details["cycle"] = cycle
        super().__init__(
            message=message,
            details=details,
            **kwargs,
        )


class ModuleVisibilityError(ModuleError):
    """A provider depends on a service not visible to its module.

    Raised when a provider in module A tries to inject a type that
    is registered by module B but not exported by B, even though
    A imports B.
    """

    _code = "QK_ERR_MOD_005"

    def __init__(
        self,
        message: str = "Service not visible to module",
        *,
        consumer_module: str | None = None,
        provider_module: str | None = None,
        service_type: str | None = None,
        **kwargs: Any,
    ) -> None:
        details = kwargs.pop("details", {})
        if consumer_module:
            details["consumer_module"] = consumer_module
        if provider_module:
            details["provider_module"] = provider_module
        if service_type:
            details["service_type"] = service_type
        super().__init__(
            message=message,
            details=details,
            **kwargs,
        )


class ModuleDuplicateError(ModuleError):
    """The same module appears twice with conflicting configurations.

    Raised when two :class:`DynamicModule` entries reference the same
    module class but with different provider lists, exports, or
    other configuration.
    """

    _code = "QK_ERR_MOD_006"

    def __init__(
        self,
        message: str = "Duplicate module with conflicting configuration",
        *,
        module_name: str | None = None,
        **kwargs: Any,
    ) -> None:
        details = kwargs.pop("details", {})
        if module_name:
            details["module"] = module_name
        super().__init__(
            message=message,
            details=details,
            **kwargs,
        )


__all__ = [
    "ModuleCycleError",
    "ModuleDuplicateError",
    "ModuleError",
    "ModuleExportError",
    "ModuleImportError",
    "ModuleVisibilityError",
    "ProviderError",
]
