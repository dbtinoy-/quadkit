"""Diagnostic error formatting for module compilation.

Every error message follows the standard:

1. **What** — the specific problem
2. **Where** — which module, which import chain
3. **Why** — why this is invalid
4. **Fix** — concrete suggestion(s)

These functions produce the *message* string for the exception classes
in ``quadkit.contracts.exceptions.provider``.  The compiler calls
these functions to construct rich error messages before raising.
"""

from __future__ import annotations

from quadkit.contracts.constants import DOCS_BASE_URL


def format_cycle_error(cycle: list[str]) -> str:
    """Format a circular module dependency error.

    Args:
        cycle: Module names forming the cycle, e.g. ``["A", "B", "C", "A"]``.
            The last element should equal the first to show the cycle closure.

    Returns:
        Multi-line diagnostic string.

    Example output::

        Circular module dependency detected.

          AuthModule → SessionModule → AuthModule

        Break the cycle by:
          1. Extract shared types into a separate module
          2. Remove the circular import from one side
    """
    chain = " → ".join(cycle)
    return (
        f"Circular module dependency detected.\n"
        f"\n"
        f"  {chain}\n"
        f"\n"
        f"Break the cycle by:\n"
        f"  1. Extract shared types into a separate module\n"
        f"  2. Remove the circular import from one side\n"
        f"\n"
        f"Reference: {DOCS_BASE_URL}/modules#cycles"
    )


def format_missing_import_error(
    module_name: str,
    missing_name: str,
    available: list[str],
) -> str:
    """Format a missing module import error.

    Args:
        module_name: The module that declares the import.
        missing_name: The module name that is not in the graph.
        available: Names of all modules in the graph.

    Returns:
        Multi-line diagnostic string.

    Example output::

        BillingModule imports 'PaymentModule', but PaymentModule is not
        registered in the module graph.

        Registered modules: AppModule, AuthModule, BillingModule, InfraModule

        To fix:
          1. Add PaymentModule to your create_app() via app.add_module()
          2. Or remove PaymentModule from BillingModule.imports
    """
    available_str = ", ".join(sorted(available)) if available else "(none)"
    return (
        f"{module_name} imports '{missing_name}', but {missing_name} is not "
        f"registered in the module graph.\n"
        f"\n"
        f"Registered modules: {available_str}\n"
        f"\n"
        f"To fix:\n"
        f"  1. Add {missing_name} to your create_app() via app.add_module()\n"
        f"  2. Or remove {missing_name} from {module_name}.imports\n"
        f"\n"
        f"Reference: {DOCS_BASE_URL}/modules#imports"
    )


def format_missing_export_error(
    module_name: str,
    export_name: str,
    provider_names: list[str],
    registered_types: list[str],
) -> str:
    """Format a missing module export error.

    Args:
        module_name: The module declaring the export.
        export_name: The type name that is not registered.
        provider_names: Names of providers in this module.
        registered_types: Type names actually registered by those providers.

    Returns:
        Multi-line diagnostic string.

    Example output::

        CacheModule declares export 'CacheBackendProtocol', but no provider in
        CacheModule registered a binding for CacheBackendProtocol.

        CacheModule providers: [CacheProvider]
        Registered types: [CacheKeyBuilderProtocol, CacheStatsCollector]

        To fix:
          1. Add CacheBackendProtocol to CacheProvider.register()
          2. Or remove CacheBackendProtocol from CacheModule.exports
    """
    providers_str = ", ".join(provider_names) if provider_names else "(none)"
    registered_str = (
        ", ".join(sorted(registered_types)) if registered_types else "(none)"
    )
    return (
        f"{module_name} declares export '{export_name}', but no provider in "
        f"{module_name} registered a binding for {export_name}.\n"
        f"\n"
        f"{module_name} providers: [{providers_str}]\n"
        f"Registered types: [{registered_str}]\n"
        f"\n"
        f"To fix:\n"
        f"  1. Add {export_name} to a provider's register() method\n"
        f"  2. Or remove {export_name} from {module_name}.exports"
    )


def format_visibility_error(
    consumer_module: str,
    consumer_provider: str,
    provider_module: str | list[str] | None,
    service_type: str,
    exported_types: list[str],
    consumer_imports: list[str] | None = None,
) -> str:
    """Format a module visibility violation error.

    Args:
        consumer_module: Module whose provider has the dependency.
        consumer_provider: The provider class name with the dependency.
        provider_module: Module that owns the service.
        service_type: The type that is not visible.
        exported_types: Types that *are* exported by the provider module.

    Returns:
        Multi-line diagnostic string.

    Example output::

        BillingProvider (in BillingModule) depends on 'TokenService'
        via constructor injection.

        TokenService is registered by AuthModule but NOT exported.

        AuthModule exports: [AuthServiceProtocol]

        To fix:
          1. Add TokenService to AuthModule.exports
          2. Or depend on AuthServiceProtocol instead (which IS exported)
    """
    exported_by = (
        ", ".join(provider_module)
        if isinstance(provider_module, list)
        else provider_module or "(none)"
    )
    exported_str = ", ".join(sorted(exported_types)) if exported_types else "(none)"
    imports_str = f"[{', '.join(consumer_imports)}]" if consumer_imports else "[]"
    return (
        f"{service_type!r} is not visible in {consumer_module!r}\n"
        f"\n"
        f"  Requested by: {consumer_provider}\n"
        f"  Exported by: {exported_by}\n"
        f"  {consumer_module} currently imports: {imports_str}\n"
        f"  Exported services available there: [{exported_str}]\n"
        f"\n"
        f"  To fix:\n"
        f"  Fix one of:\n"
        f"    1. Add the exporting module to {consumer_module}.imports\n"
        f"    2. Make the exporting module global with @module(is_global=True)\n"
        f"    3. Depend on a service that is already exported\n"
        f"\n"
        f"  Reference: {DOCS_BASE_URL}/modules#visibility"
    )


def format_duplicate_module_error(
    module_name: str,
    first_source: str,
    second_source: str,
) -> str:
    """Format a duplicate module configuration error.

    Args:
        module_name: The module class name.
        first_source: Description of the first registration.
        second_source: Description of the second registration.

    Returns:
        Multi-line diagnostic string.

    Example output::

        Module 'DatabaseModule' appears twice with different configurations.

        First:  app.add_module(DatabaseModule.configure(url="sqlite:///a.db"))
        Second: app.add_module(DatabaseModule.configure(url="sqlite:///b.db"))

        A module class can only be configured once.  To fix:
          1. Remove one of the add_module() calls
          2. Or merge the configurations into a single configure() call
    """
    return (
        f"Module '{module_name}' appears twice with different configurations.\n"
        f"\n"
        f"First:  {first_source}\n"
        f"Second: {second_source}\n"
        f"\n"
        f"A module class can only be configured once.  To fix:\n"
        f"  1. Remove one of the add_module() calls\n"
        f"  2. Or merge the configurations into a single configure() call\n"
        f"\n"
        f"Reference: {DOCS_BASE_URL}/modules#configuration"
    )


def format_not_a_module_error(
    name: str,
    entry_type: str,
) -> str:
    """Format an invalid module input error.

    Args:
        name: Name or repr of the invalid entry.
        entry_type: The actual type name of the entry.

    Returns:
        Multi-line diagnostic string.
    """
    return (
        f"'{name}' ({entry_type}) is not a valid module.\n"
        f"\n"
        f"A module must be either:\n"
        f"  1. A class decorated with @module()\n"
        f"  2. A DynamicModule from a factory method like Module.configure()\n"
        f"\n"
        f"Example:\n"
        f"  @module(providers=[MyProvider], exports=[MyProtocol])\n"
        f"  class {name}: ...\n"
        f"\n"
        f"  Or: app.add_module({name}.configure(config))"
    )
