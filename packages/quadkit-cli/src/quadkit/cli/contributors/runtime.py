from __future__ import annotations

from dataclasses import dataclass, field
from importlib.metadata import entry_points
import traceback
from typing import Any

from quadkit.cli.package_names import PUBLIC_DISTRIBUTIONS
from quadkit.contracts.cli.contributions import (
    CommandContribution,
    DoctorCheckContribution,
    HealthCheckContribution,
    HookContribution,
    SchemaSetupContribution,
    ShellContextContribution,
)
from quadkit.contracts.cli.protocols import CliContributorProtocol
from quadkit.contracts.cli.types import GeneratorDefinition

ENTRY_POINT_GROUP = "quadkit.cli.contributors"

_BUILTIN_DIST = "quadkit-cli"

_RESERVED_COMMANDS: dict[str, str] = {
    "search": "search",
}
_SCOPE_DISTS = PUBLIC_DISTRIBUTIONS


@dataclass(frozen=True)
class LoadError:
    contributor_id: str
    stage: str
    exception: str
    traceback_str: str = ""


@dataclass(frozen=True)
class CommandConflict:
    name: str
    winner: str
    losers: list[str]


@dataclass
class ContributorRuntime:
    contributors: list[CliContributorProtocol] = field(default_factory=list)
    errors: dict[str, LoadError] = field(default_factory=dict)
    command_conflicts: dict[str, CommandConflict] = field(default_factory=dict)

    _commands: list[CommandContribution] | None = None
    _generators: list[GeneratorDefinition] | None = None
    _health_checks: list[HealthCheckContribution] | None = None
    _doctor_checks: list[DoctorCheckContribution] | None = None
    _shell_contexts: list[ShellContextContribution] | None = None
    _hooks: list[HookContribution] | None = None
    _schema_setups: list[SchemaSetupContribution] | None = None

    @classmethod
    def from_entry_points(cls, group: str = ENTRY_POINT_GROUP) -> ContributorRuntime:
        runtime = cls()
        eps = entry_points(group=group)

        for ep in eps:
            contributor_id = ep.name or "<unknown>"
            try:
                contributor_cls = ep.load()
            except Exception as exc:
                runtime.errors[contributor_id] = LoadError(
                    contributor_id=contributor_id,
                    stage="load",
                    exception=str(exc),
                    traceback_str=traceback.format_exc(),
                )
                continue

            try:
                contributor = contributor_cls()
            except Exception as exc:
                runtime.errors[contributor_id] = LoadError(
                    contributor_id=contributor_id,
                    stage="factory",
                    exception=str(exc),
                    traceback_str=traceback.format_exc(),
                )
                continue

            runtime.contributors.append(contributor)

        return runtime

    @property
    def commands(self) -> list[CommandContribution]:
        if self._commands is None:
            self._commands = []
            self._resolve_command_conflicts()
        return list(self._commands)

    @property
    def generators(self) -> list[GeneratorDefinition]:
        if self._generators is None:
            self._generators = []
            for c in self.contributors:
                self._generators.extend(c.get_generators())
        return list(self._generators)

    @property
    def health_checks(self) -> list[HealthCheckContribution]:
        if self._health_checks is None:
            self._health_checks = []
            for c in self.contributors:
                self._health_checks.extend(getattr(c, "get_health_checks", list)())
        return list(self._health_checks)

    @property
    def doctor_checks(self) -> list[DoctorCheckContribution]:
        if self._doctor_checks is None:
            self._doctor_checks = []
            for c in self.contributors:
                self._doctor_checks.extend(getattr(c, "get_doctor_checks", list)())
        return list(self._doctor_checks)

    @property
    def shell_contexts(self) -> list[ShellContextContribution]:
        if self._shell_contexts is None:
            self._shell_contexts = []
            for c in self.contributors:
                self._shell_contexts.extend(getattr(c, "get_shell_context", list)())
        return list(self._shell_contexts)

    @property
    def hooks(self) -> list[HookContribution]:
        if self._hooks is None:
            self._hooks = []
            for c in self.contributors:
                self._hooks.extend(getattr(c, "get_hooks", list)())
        return list(self._hooks)

    @property
    def schema_setups(self) -> list[SchemaSetupContribution]:
        if self._schema_setups is None:
            self._schema_setups = []
            for c in self.contributors:
                self._schema_setups.extend(getattr(c, "get_schema_setup", list)())
        return list(self._schema_setups)

    def _resolve_command_conflicts(self) -> None:
        seen: dict[str, str] = {}
        resolved: list[CommandContribution] = []
        eps = {
            ep.name: getattr(getattr(ep, "dist", None), "name", None)
            for ep in entry_points(group=ENTRY_POINT_GROUP)
        }

        for c in self.contributors:
            for cmd in getattr(c, "get_commands", list)():
                if cmd.name in _RESERVED_COMMANDS:
                    actual_dist = eps.get(cmd.contributor)
                    is_scope = actual_dist in _SCOPE_DISTS
                    if not is_scope:
                        self.command_conflicts[cmd.name] = CommandConflict(
                            name=cmd.name,
                            winner=_RESERVED_COMMANDS[cmd.name],
                            losers=[cmd.contributor],
                        )
                        continue

                if cmd.name not in seen:
                    seen[cmd.name] = cmd.contributor
                    resolved.append(cmd)
                else:
                    existing = seen[cmd.name]
                    winner = self._pick_winner(existing, cmd.contributor, eps)
                    losers = [existing, cmd.contributor]
                    losers.remove(winner)
                    seen[cmd.name] = winner

                    self.command_conflicts[cmd.name] = CommandConflict(
                        name=cmd.name,
                        winner=winner,
                        losers=losers,
                    )

                    if winner == cmd.contributor:
                        resolved = [r for r in resolved if r.name != cmd.name]
                        resolved.append(cmd)

        self._commands = resolved

    @staticmethod
    def _pick_winner(
        existing: str,
        incoming: str,
        eps: dict[str, str | None],
    ) -> str:
        existing_dist = eps.get(existing)
        incoming_dist = eps.get(incoming)
        existing_scope = existing_dist in _SCOPE_DISTS
        incoming_scope = incoming_dist in _SCOPE_DISTS
        if existing_scope and not incoming_scope:
            return existing
        if incoming_scope and not existing_scope:
            return incoming
        return existing

    def register_commands(
        self,
        app: Any,
        builtin_names: frozenset[str],
    ) -> None:
        from importlib import import_module

        for cmd in self.commands:
            if cmd.name in builtin_names:
                continue
            try:
                module_path, _, factory_name = cmd.app_factory_path.partition(":")
                mod = import_module(module_path)
                factory = getattr(mod, factory_name)
                sub_app = factory()
                app.add_typer(sub_app, name=cmd.name, help=cmd.help)
            except Exception as exc:
                self.errors[cmd.name] = LoadError(
                    contributor_id=cmd.contributor,
                    stage="factory",
                    exception=f"Failed to register command {cmd.name}: {exc}",
                    traceback_str=traceback.format_exc(),
                )
