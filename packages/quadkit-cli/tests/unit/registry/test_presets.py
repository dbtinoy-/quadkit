from __future__ import annotations

from typing import Any, ClassVar

import pytest

from quadkit.cli.registry import presets as presets_module
from quadkit.cli.registry.presets import (
    FullStackPreset,
    GraphQLPreset,
    MicroservicePreset,
    MinimalPreset,
    Preset,
    PresetDefinition,
    PresetRegistry,
    WebAPIPreset,
    WorkerPreset,
)


class TestPresetDefinition:
    def test_abc_cannot_be_instantiated(self) -> None:
        with pytest.raises(TypeError):
            PresetDefinition()  # type: ignore[abstract]

    def test_built_in_presets_carry_name_description_and_packages(self) -> None:
        for preset_class in (
            MinimalPreset,
            WebAPIPreset,
            GraphQLPreset,
            WorkerPreset,
            FullStackPreset,
            MicroservicePreset,
        ):
            preset = preset_class().get_preset()
            assert isinstance(preset, Preset)
            assert preset.name == preset_class.name
            assert preset.description == preset_class.description
            assert preset.packages == preset_class.packages

    def test_get_preset_returns_independent_copies(self) -> None:
        first = MinimalPreset().get_preset()
        second = MinimalPreset().get_preset()

        first.packages.append("quadkit-web")
        first.config["web"] = {"port": 1}

        assert "quadkit-web" not in second.packages
        assert second.config == {}
        assert MinimalPreset.packages == ["quadkit"]


class TestPresetRegistry:
    def test_empty_when_constructed_directly(self) -> None:
        registry = PresetRegistry()

        assert registry.get_all() == {}
        assert registry.get_choices() == []
        assert registry.get("minimal") is None

    def test_register_and_get(self) -> None:
        registry = PresetRegistry()
        registry.register(MinimalPreset)

        preset = registry.get("minimal")

        assert preset is not None
        assert preset.name == "minimal"
        assert registry.get_choices() == ["minimal"]

    def test_register_overwrites_same_name(self) -> None:
        registry = PresetRegistry()

        class _CustomMinimal(PresetDefinition):
            name = "minimal"
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

        registry.register(MinimalPreset)
        registry.register(_CustomMinimal)

        preset = registry.get("minimal")

        assert registry.get_choices() == ["minimal"]
        assert preset is not None
        assert preset.description == "custom"

    def test_with_defaults_registers_the_installed_presets(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(presets_module, "provider_available", lambda _f: True)

        registry = PresetRegistry.with_defaults()

        assert registry.get_choices() == [
            "minimal",
            "web-api",
            "graphql",
            "worker",
            "fullstack",
            "microservice",
        ]

    def test_optional_presets_need_their_providers(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(presets_module, "provider_available", lambda _f: False)

        registry = PresetRegistry.with_defaults()

        assert registry.get_choices() == ["minimal", "web-api"]
