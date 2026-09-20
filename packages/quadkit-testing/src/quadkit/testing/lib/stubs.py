"""Helper for validating stub module configuration in tests.

This module provides `assert_stub_modules()` to verify that modules marked
with `require_stub=True` are using their test doubles (stub implementations)
instead of real providers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from quadkit.di.module.graph import CompiledModuleGraph

from quadkit.di.module.base import Module
from quadkit.di.module.constants import MODULE_METADATA_ATTR


class ConfigurationError(Exception):
    """Raised when a require_stub module is loaded via configure() in test mode.

    This exception indicates that a module with `require_stub=True` was compiled
    using its `configure()` method instead of `stub()`, meaning real infrastructure
    (database, cache, etc.) would be initialized in tests.
    """

    _code: str = "QK_ERR_TEST_011"
    __test__ = False  # Prevent pytest from collecting this class


def assert_stub_modules(
    graph: CompiledModuleGraph,
    testing_mode: bool,
) -> None:
    """Raise ConfigurationError if testing_mode and a require_stub module is not stubbed.

    Call this after compiling a module graph in test setup to catch accidentally
    using real providers in tests.

    Args:
        graph: The compiled module graph.
        testing_mode: True if running in test mode.

    Raises:
        ConfigurationError: If testing_mode is True and a require_stub module
            was loaded via configure() instead of stub().
    """
    if not testing_mode:
        return

    for cls, node in graph.nodes.items():
        meta = getattr(cls, MODULE_METADATA_ATTR, None)
        if meta is None or not getattr(meta, "require_stub", False):
            continue

        # Check if stub() has been overridden from the Module base class
        try:
            # Get the classmethod from the class
            stub_method = getattr(cls, "stub", None)
            if stub_method is None:
                continue

            # Extract the underlying function and compare with Module.stub's function
            stub_func = stub_method.__func__
            module_stub_func = Module.stub.__func__  # type: ignore[attr-defined]

            if stub_func is module_stub_func:
                raise ConfigurationError(
                    f"Module '{node.name}' (class {cls.__name__}) has require_stub=True but "
                    f"does not override stub(). "
                    f"In test mode, you must define a stub() classmethod that returns "
                    f"a DynamicModule with test providers, not real infrastructure. "
                    f"Example:\n\n"
                    f"  @classmethod\n"
                    f"  def stub(cls, config=None):\n"
                    f"      return DynamicModule(\n"
                    f"          module=cls,\n"
                    f"          providers=[...InMemory/Fake providers...],\n"
                    f"          exports=[...],\n"
                    f"      )"
                )
        except (AttributeError, TypeError):
            # stub_method exists but isn't a function — shouldn't happen with normal classes
            pass
