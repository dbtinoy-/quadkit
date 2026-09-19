from dataclasses import dataclass

import pytest

from quadkit.di.module import create_module


@dataclass
class ProviderX:
    name = "provider_x"


def test_module_system_full_verification():
    """Test that module system correctly configures builder with providers and imports."""
    # Define modules
    @create_module(name="dep", providers=[ProviderX])
    class DepMod:
        pass

    @create_module(name="main", imports=[DepMod])
    class MainMod:
        pass

    # Builder stub
    class MockBuilder:
        def __init__(self):
            self.added_providers = []
            self._modules = set()

        def add_provider(self, provider):
            self.added_providers.append(provider)

        def add_module(self, module_cls):
            self._modules.add(module_cls)

    builder = MockBuilder()

    # Configure both modules as orchestrator would
    DepMod.__quadkit_module__.configure_builder(builder)
    MainMod.__quadkit_module__.configure_builder(builder)

    # Verify that provider and import were registered
    assert any(isinstance(p, ProviderX) for p in builder.added_providers)
    assert DepMod in builder._modules


def test_non_module_import_raises_type_error():
    """Importing a non-module-decorated class raises TypeError at construction."""
    with pytest.raises(TypeError, match="not a class"):

        @create_module(name="broken", imports=["ghost"])
        class BrokenMod:
            pass
