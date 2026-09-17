"""CLI cold-start pins (plans/09172026 C-01..C-04).

Pins the lazy command resolution introduced in ``quadkit.cli.runtime.main``:

- Importing the CLI entry point must not import any command module, the
  CLI-context chain, the registry submodules, or the framework
  (``quadkit.security``/``quadkit.web``/...) — and neither must ``--help``.
- ``quadkit version`` dispatches with unchanged output.
- Every static table entry resolves to a real command.
- Contributed commands still register via the scan-on-miss path.
"""

from __future__ import annotations

import importlib
import subprocess
import sys
from typing import Any

import pytest
from typer.testing import CliRunner

from quadkit.cli.runtime.main import (
    _BUILTIN_COMMANDS,
    _COMMAND_TABLE,
    LazyQuadkitGroup,
    app,
)

_BANNED_PREFIXES = (
    "quadkit.cli.commands.",
    "quadkit.cli.scaffold",
    "quadkit.cli.runtime.context",
    "quadkit.cli.registry.",
    "quadkit.security",
    "quadkit.web",
    "quadkit.validation",
    "quadkit.testing",
    "quadkit.config",
    "quadkit.serialization",
)


def _banned_modules() -> list[str]:
    return sorted(
        name
        for name in sys.modules
        if name.startswith(_BANNED_PREFIXES)
        # the entry-point module itself is expected
        and name != "quadkit.cli.runtime.main"
    )


class TestImportIsolation:
    """C-01/C-03 — importing (or helping) the CLI imports no commands."""

    def test_import_main_is_clean(self) -> None:
        code = (
            "import sys\n"
            "import quadkit.cli.runtime.main\n"
            "banned = [n for n in sys.modules if n.startswith("
            "    ('quadkit.cli.commands.', 'quadkit.cli.scaffold',"
            "     'quadkit.cli.runtime.context', 'quadkit.cli.registry.',"
            "     'quadkit.security', 'quadkit.web', 'quadkit.validation',"
            "     'quadkit.testing', 'quadkit.config',"
            "     'quadkit.serialization'))]\n"
            "print(','.join(banned))\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "", (
            f"importing quadkit.cli.runtime.main pulled in: {result.stdout}"
        )

    def test_help_does_not_import_command_modules(self) -> None:
        code = (
            "import io, contextlib, sys\n"
            "from quadkit.cli.runtime.main import app\n"
            "buf = io.StringIO()\n"
            "with contextlib.redirect_stdout(buf):\n"
            "    try:\n"
            "        app(['--help'], standalone_mode=False)\n"
            "    except SystemExit:\n"
            "        pass\n"
            "banned = [n for n in sys.modules if n.startswith("
            "    'quadkit.cli.commands.')]\n"
            "print(','.join(banned))\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "", (
            f"--help imported command modules: {result.stdout}"
        )


class TestDispatch:
    """C-01 — lazy dispatch keeps the CLI surface identical."""

    def test_version_output(self) -> None:
        from quadkit.cli.constants import __version__

        result = CliRunner().invoke(app, ["version"])
        assert result.exit_code == 0
        assert "quadkit" in result.output
        assert __version__ in result.output

    def test_unknown_command_still_errors(self) -> None:
        result = CliRunner().invoke(app, ["definitely-not-a-command"])
        assert result.exit_code == 2
        assert "No such command" in result.output

    def test_builtin_names_unchanged(self) -> None:
        assert "deploy" not in _BUILTIN_COMMANDS
        assert {"health", "doctor"} <= _BUILTIN_COMMANDS
        assert set(_COMMAND_TABLE) | {"health", "doctor"} == set(_BUILTIN_COMMANDS)


class TestCommandTable:
    """Every table entry resolves — no dead paths."""

    @pytest.mark.parametrize("name", sorted(_COMMAND_TABLE))
    def test_entry_resolves(self, name: str) -> None:
        module_path, attr, help_text = _COMMAND_TABLE[name]
        assert help_text, f"{name} must carry help text for lazy listings"

        module = importlib.import_module(module_path)
        obj = getattr(module, attr)

        import typer

        assert isinstance(obj, typer.Typer) or callable(obj), (
            f"{module_path}:{attr} is neither a Typer app nor a callable"
        )


class TestLazyGroup:
    """The stub serves listings without importing; materializes on use."""

    def test_stub_is_light(self) -> None:
        entry = _COMMAND_TABLE["version"]
        from quadkit.cli.runtime.main import _LazyBuiltinCommand

        stub = _LazyBuiltinCommand(
            name="version",
            module_path=entry[0],
            attr=entry[1],
            help_text=entry[2],
        )
        assert stub.name == "version"
        assert stub.hidden is False
        listing_help = stub.short_help or stub.help or ""
        assert "versions" in listing_help
        # Not materialized by listing attributes.
        assert stub.__dict__.get("_lazy_real") is None

    def test_materialize_on_use_and_cache(self) -> None:
        entry = _COMMAND_TABLE["version"]
        from quadkit.cli.runtime.main import _LazyBuiltinCommand

        stub = _LazyBuiltinCommand(
            name="version",
            module_path=entry[0],
            attr=entry[1],
            help_text=entry[2],
        )
        callback = stub.callback  # triggers materialization
        assert callback is not None
        real = stub.__dict__["_lazy_real"]
        assert real is not None
        assert stub.callback is real.callback

    def test_unknown_name_resolves_none_after_scan(self) -> None:
        group = LazyQuadkitGroup(name="quadkit")
        ctx: Any = None
        assert group.get_command(ctx, "definitely-not-a-command") is None


class TestContributedScanOnMiss:
    """C-04 — contributed commands register lazily via the capture shim."""

    def test_contributed_command_dispatches(self, monkeypatch) -> None:
        import typer

        from quadkit.cli.contributors import runtime as contributor_runtime

        marker = {"called": False}

        contributed = typer.Typer()

        @contributed.command()
        def probe() -> None:
            marker["called"] = True

        class _FakeRuntime:
            def register_commands(
                self, target: Any, builtin_names: frozenset[str]
            ) -> None:
                target.add_typer(contributed, name="zz-fake-contrib")

        monkeypatch.setattr(
            contributor_runtime.ContributorRuntime,
            "from_entry_points",
            classmethod(lambda cls: _FakeRuntime()),  # noqa: ARG005,
        )

        result = CliRunner().invoke(app, ["zz-fake-contrib", "probe"])
        assert result.exit_code == 0, result.output
        assert marker["called"] is True


__all__ = [
    "TestCommandTable",
    "TestContributedScanOnMiss",
    "TestDispatch",
    "TestImportIsolation",
    "TestLazyGroup",
]
