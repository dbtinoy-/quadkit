"""DI container validator — validation and diagnostics."""

from __future__ import annotations

from typing import Any

from quadkit.contracts.core.scopes import ServiceScope
from quadkit.contracts.exceptions.container import (
    OrphanedRegistration as OrphanedRegistration,
)
from quadkit.di.resolution.registry import ServiceRegistry
from quadkit.di.resolution.type_hints import TypeHintResolverImpl
from quadkit.logging import get_logger

logger = get_logger(__name__)


class ContainerValidator:
    """Container validation and diagnostics.

    Checks for missing dependencies, circular references, scope violations,
    and orphaned registrations.

    Args:
        registry: The shared service registry to validate.
        type_hint_resolver: Resolver for extracting type dependency information.
    """

    def __init__(
        self, registry: ServiceRegistry, type_hint_resolver: TypeHintResolverImpl
    ) -> None:
        self._registry = registry
        self._type_hint_resolver = type_hint_resolver

    def validate(self) -> list[str]:
        """Validate the container configuration.

        Checks:
        - All registered services have resolvable dependencies
        - No circular dependencies across the entire graph
        - No scope violations (singleton depending on scoped/transient)

        Returns:
            List of validation issues (empty if valid).
        """
        issues: list[str] = self._registry.validate_graph()

        for descriptor in self._registry.all():
            service_type = descriptor.service_type
            service_name = getattr(service_type, "__name__", str(service_type))

            if descriptor.scope == ServiceScope.SINGLETON:
                if descriptor.implementation is None:
                    continue

                try:
                    deps = self._type_hint_resolver.get_type_dependencies(
                        descriptor.implementation,
                    )
                    for dep_type in deps:
                        dep_desc = self._registry.get(dep_type)
                        if dep_desc and dep_desc.scope != ServiceScope.SINGLETON:
                            issues.append(
                                f"Scope violation: Singleton '{service_name}' depends on "
                                f"{dep_desc.scope.value} '{getattr(dep_type, '__name__', str(dep_type))}'",
                            )
                except TypeError as e:
                    if "unhashable" in str(e):
                        # Type hint produces an unhashable value — resolver issue,
                        # not something the user can fix with annotations.
                        logger.warning(
                            "validate.scope_check_unhashable_hint",
                            service=service_name,
                            error=str(e),
                        )
                    else:
                        # Factory functions or lambdas without type hints —
                        # surface as validation issue so operators know to add
                        # type annotations to enable scope checking.
                        issues.append(
                            f"Scope analysis incomplete: Singleton '{service_name}' uses an "
                            f"implementation without analyzable type hints ({type(e).__name__}: {e}). "
                            f"Add type annotations to the constructor to enable scope validation."
                        )
                except AttributeError as e:
                    logger.warning(
                        "validate.scope_check_attribute_error",
                        service=service_name,
                        error=str(e),
                    )
                except (KeyError, ValueError) as e:
                    logger.warning(
                        "validate.scope_check_resolution_error",
                        service=service_name,
                        error=str(e),
                    )

        return issues

    def validate_no_orphans(self) -> list[OrphanedRegistration]:
        """Find registrations that no other service depends on.

        Returns:
            List of potentially orphaned registrations.
        """
        depended_upon: set[Any] = set()

        for descriptor in self._registry.all():
            service_type = descriptor.service_type
            if descriptor.implementation is None:
                continue

            try:
                deps = self._type_hint_resolver.get_type_dependencies(
                    descriptor.implementation,
                )
                for dep in deps:
                    try:
                        hash(dep)
                        depended_upon.add(dep)
                    except TypeError:
                        pass
            except (AttributeError, TypeError, KeyError, ValueError) as e:
                logger.debug(
                    "validate_no_orphans.dep_resolution_error",
                    service=getattr(service_type, "__name__", str(service_type)),
                    error=str(e),
                )
                continue

        orphans: list[OrphanedRegistration] = []

        for service_type in (d.service_type for d in self._registry.all()):
            try:
                if service_type in depended_upon:
                    continue
            except TypeError:
                pass

            service_name = getattr(service_type, "__name__", str(service_type))
            module_name = getattr(service_type, "__module__", "")

            if not module_name or module_name.startswith("builtins"):
                continue

            suggestion = (
                f"Either use '{service_name}' in another service's constructor "
                f"or remove the registration."
            )

            orphans.append(
                OrphanedRegistration(
                    service_key=f"{module_name}.{service_name}",
                    registered_at=module_name,
                    suggestion=suggestion,
                )
            )

        return orphans


__all__ = ["ContainerValidator", "OrphanedRegistration"]
