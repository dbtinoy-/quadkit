from quadkit.config import QuadkitConfig
from quadkit.config.lib import ConfigRegistry
from quadkit.domain import DomainModel
from dataclasses import dataclass


@dataclass(init=False)
class ExtensionA(DomainModel):
    key_a: str = "default_a"

@dataclass(init=False)
class ExtensionB(DomainModel):
    key_b: str = "default_b"

def test_config_registry_scoping():
    # Instance 1 with Extension A
    registry1 = ConfigRegistry()
    registry1.register("ext", ExtensionA)

    config1 = QuadkitConfig(ext={"key_a": "custom_a"})
    registry1.apply_to_instance(config1)

    # Instance 2 with Extension B (same section name 'ext')
    registry2 = ConfigRegistry()
    registry2.register("ext", ExtensionB)

    config2 = QuadkitConfig(ext={"key_b": "custom_b"})
    registry2.apply_to_instance(config2)

    # Verify that config1 resolves to ExtensionA
    section1 = config1.get_section("ext")
    assert isinstance(section1, ExtensionA)
    assert section1.key_a == "custom_a"

    # Verify that config2 resolves to ExtensionB
    section2 = config2.get_section("ext")
    assert isinstance(section2, ExtensionB)
    assert section2.key_b == "custom_b"

    # Verify no global leaked state (if we used global state, one would overwrite the other)
    assert section1 != section2

def test_config_get_section_explicit_model():
    config = QuadkitConfig(custom={"val": 123})

    @dataclass(init=False)
    class CustomModel(DomainModel):
        val: int

    # Explicit model should work regardless of registry
    section = config.get_section("custom", CustomModel)
    assert isinstance(section, CustomModel)
    assert section.val == 123

def test_config_registry_list_extensions():
    registry = ConfigRegistry()
    registry.register("a", ExtensionA)
    registry.register("b", ExtensionB)

    assert "a" in registry.list_extensions()
    assert "b" in registry.list_extensions()
    assert len(registry.list_extensions()) == 2
