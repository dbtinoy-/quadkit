"""Completion registry for shell completion.

This module provides a registry pattern for generating shell completions.
"""

from __future__ import annotations

import abc


class CompletionGenerator(abc.ABC):
    """Abstract base class for completion generators."""

    name: str
    extension: str

    @abc.abstractmethod
    def generate(self, cli_app_name: str) -> str:
        """Generate completion script."""


class BashCompletionGenerator(CompletionGenerator):
    """Bash completion generator."""

    name = "bash"
    extension = "sh"

    def generate(self, cli_app_name: str) -> str:
        return f"""#!/bin/bash

# {cli_app_name} shell completion
_{cli_app_name}_completion() {{
    local cur prev opts
    COMPREPLY=()
    cur="${{COMP_WORDS[COMP_CWORD]}}"
    prev="${{COMP_WORDS[COMP_CWORD-1]}}"

    opts="$({cli_app_name} --help | grep -E '^\\s+[a-z]' | awk '{{print $1}}')"

    COMPREPLY=( $(compgen -W "${{opts}}" -- "${{cur}}") )
    return 0
}}

complete -F _{cli_app_name}_completion {cli_app_name}
"""


class ZshCompletionGenerator(CompletionGenerator):
    """Zsh completion generator."""

    name = "zsh"
    extension = "zsh"

    def generate(self, cli_app_name: str) -> str:
        return f"""# {cli_app_name} shell completion for zsh

_{cli_app_name}_completion() {{
    local -a commands
    commands=(
        "new:Create a new Quadkit project"
        "init:Initialize Quadkit in existing project"
        "dev:Start development server"
        "start:Start production server"
        "db:Database management commands"
        "gen:Code generation commands"
        "config:Configuration management"
        "project:Project management"
        "system:System information"
    )

    _describe 'command' commands
}}

compdef _{cli_app_name}_completion {cli_app_name}
"""


class FishCompletionGenerator(CompletionGenerator):
    """Fish shell completion generator."""

    name = "fish"
    extension = "fish"

    def generate(self, cli_app_name: str) -> str:
        return f"""# {cli_app_name} shell completion for fish

complete -c {cli_app_name} -f -a "
new\tCreate a new Quadkit project
init\tInitialize Quadkit in existing project
dev\tStart development server
start\tStart production server
db\tDatabase management commands
gen\tCode generation commands
config\tConfiguration management
project\tProject management
system\tSystem information
"
"""


class PowerShellCompletionGenerator(CompletionGenerator):
    """PowerShell completion generator."""

    name = "powershell"
    extension = "ps1"

    def generate(self, cli_app_name: str) -> str:
        return f"""# {cli_app_name} shell completion for PowerShell

$scriptblock = {{
    param($wordToComplete, $commandAst, $cursorPosition)
    $commands = @(
        "new", "init", "dev", "start", "db", "gen", "config", "project", "system"
    )
    $commands | Where-Object {{ $_ -like "$wordToComplete*" }} | ForEach-Object {{
        [System.Management.Automation.CompletionResult]::new($_, $_, 'ParameterValue', $_)
    }}
}}

Register-ArgumentCompleter -CommandName {cli_app_name} -ScriptBlock $scriptblock
"""


class CompletionRegistry:
    """Registry for completion generators.

    Instances are always empty — use :meth:`with_defaults` for the
    in-package built-ins or :meth:`register` for plugin generators.
    """

    def __init__(self) -> None:
        self._generators: dict[str, CompletionGenerator] = {}

    def register(self, generator: type[CompletionGenerator]) -> None:
        """Register a completion generator class."""
        instance = generator()
        self._generators[generator.name] = instance

    def get(self, name: str) -> CompletionGenerator | None:
        """Get a generator by name."""
        return self._generators.get(name)

    def get_all(self) -> dict[str, CompletionGenerator]:
        """Get all registered generators."""
        return self._generators.copy()

    def get_choices(self) -> list[str]:
        """Get list of available generator names."""
        return list(self._generators.keys())

    @classmethod
    def _default_entries(cls) -> tuple[type[CompletionGenerator], ...]:
        """The complete in-package built-in set, declared exactly once."""
        return (
            BashCompletionGenerator,
            ZshCompletionGenerator,
            FishCompletionGenerator,
            PowerShellCompletionGenerator,
        )

    @classmethod
    def with_defaults(cls) -> CompletionRegistry:
        """Return an instance populated with the built-in generators."""
        registry = cls()
        for entry in cls._default_entries():
            registry.register(entry)
        return registry


def generate_completion(shell: str, cli_app_name: str = "quadkit") -> str:
    """Generate completion script for the specified shell."""
    registry = CompletionRegistry.with_defaults()
    generator = registry.get(shell)
    if not generator:
        raise ValueError(
            f"Unknown shell: {shell}. Available: {', '.join(registry.get_choices())}",
        )
    return generator.generate(cli_app_name)


__all__ = [
    "BashCompletionGenerator",
    "CompletionGenerator",
    "CompletionRegistry",
    "FishCompletionGenerator",
    "PowerShellCompletionGenerator",
    "ZshCompletionGenerator",
    "generate_completion",
]
