from __future__ import annotations

import pytest

from quadkit.cli.registry.completion import (
    BashCompletionGenerator,
    CompletionGenerator,
    CompletionRegistry,
    FishCompletionGenerator,
    PowerShellCompletionGenerator,
    ZshCompletionGenerator,
    generate_completion,
)


class TestCompletionGenerators:
    def test_abc_cannot_be_instantiated(self) -> None:
        with pytest.raises(TypeError):
            CompletionGenerator()  # type: ignore[abstract]

    def test_built_ins_declare_a_name_and_extension(self) -> None:
        expected = {
            BashCompletionGenerator: ("bash", "sh"),
            ZshCompletionGenerator: ("zsh", "zsh"),
            FishCompletionGenerator: ("fish", "fish"),
            PowerShellCompletionGenerator: ("powershell", "ps1"),
        }

        for generator_class, (name, extension) in expected.items():
            generator = generator_class()
            assert generator.name == name
            assert generator.extension == extension

    def test_generated_scripts_name_the_cli(self) -> None:
        for generator_class in (
            BashCompletionGenerator,
            ZshCompletionGenerator,
            FishCompletionGenerator,
            PowerShellCompletionGenerator,
        ):
            script = generator_class().generate("mycli")
            assert script.startswith("#!/bin/bash") or "mycli" in script
            assert "mycli" in script


class TestCompletionRegistry:
    def test_empty_when_constructed_directly(self) -> None:
        registry = CompletionRegistry()

        assert registry.get_all() == {}
        assert registry.get_choices() == []
        assert registry.get("bash") is None

    def test_register_and_get(self) -> None:
        registry = CompletionRegistry()
        registry.register(BashCompletionGenerator)

        generator = registry.get("bash")

        assert generator is not None
        assert isinstance(generator, BashCompletionGenerator)
        assert registry.get_choices() == ["bash"]

    def test_with_defaults_registers_every_shell(self) -> None:
        registry = CompletionRegistry.with_defaults()

        assert registry.get_choices() == ["bash", "zsh", "fish", "powershell"]
        assert isinstance(registry.get("fish"), FishCompletionGenerator)


class TestGenerateCompletion:
    @pytest.mark.parametrize("shell", ["bash", "zsh", "fish", "powershell"])
    def test_script_contains_the_app_name(self, shell: str) -> None:
        script = generate_completion(shell, cli_app_name="mycli")

        assert "mycli" in script

    def test_unknown_shell_raises_with_the_available_choices(self) -> None:
        with pytest.raises(ValueError, match="Unknown shell: tcsh"):
            generate_completion("tcsh")
