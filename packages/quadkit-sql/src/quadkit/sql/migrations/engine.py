"""Migration engine for executing Alembic commands."""

from __future__ import annotations

import asyncio
from contextlib import redirect_stdout
import io
from typing import Any, cast

from quadkit.logging import get_logger

try:
    from alembic import command
    from alembic.script import (
        ScriptDirectory,
    )  # optional import required by migration helpers

    ALEMBIC_AVAILABLE = True
except ImportError:
    ALEMBIC_AVAILABLE = False

logger = get_logger(__name__)


class MigrationEngine:
    """Core engine for executing Alembic migrations."""

    def __init__(self, config: Any) -> None:
        self.config = config

    async def upgrade(
        self,
        revision: str = "head",
        sql: bool = False,
        tag: str | None = None,
    ) -> None:
        """Upgrade to a specific revision."""

        def _upgrade() -> None:
            command.upgrade(self.config, revision, sql=sql, tag=tag)

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _upgrade)

    async def downgrade(
        self,
        revision: str = "-1",
        sql: bool = False,
        tag: str | None = None,
    ) -> None:
        """Downgrade to a specific revision."""

        def _downgrade() -> None:
            command.downgrade(self.config, revision, sql=sql, tag=tag)

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _downgrade)

    async def upgrade_dry_run(self, revision: str = "head") -> list[str]:
        """Preview upgrade operations without executing them."""

        def _dry_run() -> list[str]:
            output = io.StringIO()
            with redirect_stdout(output):
                command.upgrade(self.config, revision, sql=True)
            return output.getvalue().strip().split("\n")

        loop = asyncio.get_event_loop()
        sql_commands = await loop.run_in_executor(None, _dry_run)
        return list(filter(lambda cmd: cmd.strip(), sql_commands))

    async def downgrade_dry_run(self, revision: str = "base") -> list[str]:
        """Preview downgrade operations without executing them."""

        def _dry_run() -> list[str]:
            output = io.StringIO()
            with redirect_stdout(output):
                command.downgrade(self.config, revision, sql=True)
            return output.getvalue().strip().split("\n")

        loop = asyncio.get_event_loop()
        sql_commands = await loop.run_in_executor(None, _dry_run)
        return list(filter(lambda cmd: cmd.strip(), sql_commands))

    async def create_revision(
        self,
        message: str,
        autogenerate: bool = False,
        sql: bool = False,
    ) -> str:
        """Create a new migration revision."""

        def _create_revision() -> None:
            command.revision(
                self.config,
                message=message,
                autogenerate=autogenerate,
                sql=sql,
            )

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _create_revision)
        script = ScriptDirectory.from_config(self.config)
        return str(script.get_current_head())

    async def create_branch(self, branch_name: str, message: str | None = None) -> str:
        """Create a new migration branch."""
        msg = message or f"Create branch {branch_name}"

        def _create_branch() -> None:
            command.revision(self.config, message=msg)

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _create_branch)
        script = ScriptDirectory.from_config(self.config)
        return str(script.get_current_head())

    async def merge_branches(
        self,
        source_branch: str,
        target_branch: str,
        message: str | None = None,
    ) -> str:
        """Merge one branch into another."""
        msg = message or f"Merge {source_branch} into {target_branch}"

        def _merge() -> None:
            merge_fn = cast("Any", command.merge)
            try:
                merge_fn(self.config, source_branch, target_branch, message=msg)
            except TypeError:
                merge_fn(self.config, message=msg)

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _merge)
        script = ScriptDirectory.from_config(self.config)
        return str(script.get_current_head())

    async def edit(self, revision: str) -> None:
        """Edit an existing migration revision."""

        def _edit() -> None:
            command.edit(self.config, revision)

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _edit)

    async def squash(self, revisions: list[str], message: str) -> str:
        """Squash multiple revisions into one."""

        def _squash() -> None:
            if hasattr(command, "squash"):
                command.squash(self.config, message=message, revisions=revisions)
            else:
                command.revision(self.config, message=message)

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _squash)
        script = ScriptDirectory.from_config(self.config)
        return str(script.get_current_head())
