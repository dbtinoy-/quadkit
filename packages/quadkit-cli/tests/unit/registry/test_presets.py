from __future__ import annotations

from typing import Any, ClassVar

import pytest

from quadkit.cli.registry.presets import (
    ApiPreset,
    Preset,
    PresetDefinition,
    PresetRegistry,
)


class TestPresetDefinition:
    def test_abc_cannot_be_instantiated(self) -> None:
        with pytest.raises(TypeError):
            PresetDefinition()  # type: ignore[abstract]

    def test_built_in_presets_carry_name_description_and_packages(self) -> None:
        for preset_class in (ApiPreset,):
            preset = preset_class().get_preset()
            assert isinstance(preset, Preset)
            assert preset.name == preset_class.name
            assert preset.description == preset_class.description
            assert preset.packages == preset_class.packages

    def test_get_preset_returns_independent_copies(self) -> None:
        first = ApiPreset().get_preset()
        second = ApiPreset().get_preset()

        first.packages.append("quadkit-auth")
        first.config["web"] = {"port": 1}

        assert "quadkit-auth" not in second.packages
        assert second.config["web"]["port"] == 8000


class TestPresetRegistry:
    def test_empty_when_constructed_directly(self) -> None:
        registry = PresetRegistry()

        assert registry.get_all() == {}
        assert registry.get_choices() == []
        assert registry.get("api") is None

    def test_register_and_get(self) -> None:
        registry = PresetRegistry()
        registry.register(ApiPreset)

        preset = registry.get("api")

        assert preset is not None
        assert preset.name == "api"
        assert registry.get_choices() == ["api"]

    def test_register_overwrites_same_name(self) -> None:
        registry = PresetRegistry()

        class _CustomApi(PresetDefinition):
            name = "api"
            description = "custom"
            packages: ClassVar[list[str]] = ["quadkit-web"]
            config: ClassVar[dict[str, Any]] = {}

            def get_preset(self) -> Preset:
                return Preset(
                    name=self.name,
                    description=self.description,
                    packages=self.packages.copy(),
                    config=self.config.copy(),
                )

        registry.register(ApiPreset)
        registry.register(_CustomApi)

        preset = registry.get("api")

        assert registry.get_choices() == ["api"]
        assert preset is not None
        assert preset.description == "custom"

    def test_with_defaults_registers_the_single_preset(self) -> None:
        registry = PresetRegistry.with_defaults()

        assert registry.get_choices() == ["api"]
        assert registry.get("api") is not None
