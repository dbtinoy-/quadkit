"""Exceptions for the DI subsystem.

Re-exports all container contract exceptions plus the module/provider
error bases.
"""

from __future__ import annotations

from quadkit.contracts.exceptions import ModuleError as ModuleError
from quadkit.contracts.exceptions import ProviderError as ProviderError
from quadkit.contracts.exceptions.container import (
    CircularDependencyError as CircularDependencyError,
)
from quadkit.contracts.exceptions.container import (
    ContainerBuildError as ContainerBuildError,
)
from quadkit.contracts.exceptions.container import ContainerError as ContainerError
from quadkit.contracts.exceptions.container import DependencyError as DependencyError
from quadkit.contracts.exceptions.container import (
    RegistrationError as RegistrationError,
)
from quadkit.contracts.exceptions.container import (
    UnresolvableDependencyError as UnresolvableDependencyError,
)

__all__ = [
    "CircularDependencyError",
    "ContainerBuildError",
    "ContainerError",
    "DependencyError",
    "ModuleError",
    "ProviderError",
    "RegistrationError",
    "UnresolvableDependencyError",
]
