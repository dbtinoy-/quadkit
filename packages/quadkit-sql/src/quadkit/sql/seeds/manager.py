"""Seed manager for executing and tracking data seeds."""

from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path
from typing import Any, Protocol, Self

import anyio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from quadkit.logging import get_logger
from quadkit.sql.exceptions import DatabaseError, QueryError

logger = get_logger(__name__)


class SeedFileHandler(Protocol):
    """Protocol for seed file handlers."""

    async def execute(self, file_path: Path, engine: Any) -> None: ...


class SQLSeedHandler:
    """Handler for SQL seed files."""

    async def execute(self, file_path: Path, engine: Any) -> None:
        """Execute a raw SQL seed file."""

        logger.info("Executing SQL seed: %s", file_path.name)
        async_path = anyio.Path(file_path)
        sql_content = await async_path.read_text(encoding="utf-8")

        # Better split that handles dollar quoting for PostgreSQL
        statements = []
        current_statement = []
        in_dollar_block = False

        for line in sql_content.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("--"):
                continue

            # Toggle dollar quoting state
            if "$" in line:
                in_dollar_block = not in_dollar_block

            current_statement.append(line)

            # End of statement: semicolon found and not inside a dollar block
            if stripped.endswith(";") and not in_dollar_block:
                statements.append("\n".join(current_statement))
                current_statement = []

        if current_statement:
            remaining = "\n".join(current_statement).strip()
            if remaining and not remaining.startswith("--"):
                statements.append(remaining)

        async with engine.begin() as conn:
            for statement in statements:
                if not statement.strip():
                    continue
                # Escape colons to prevent SQLAlchemy from treating them as bind parameters
                # This is common in JSON strings and PostgreSQL type casts (::jsonb)
                escaped_statement = statement.replace(":", "\\:")
                await conn.execute(text(escaped_statement))


class PythonSeedHandler:
    """Handler for Python seed scripts."""

    async def execute(self, file_path: Path, engine: Any) -> None:
        """Execute a Python seed script."""
        logger.info("Executing Python seed: %s", file_path.name)

        # Load module dynamically
        spec = importlib.util.spec_from_file_location("seed_module", file_path)
        if not spec or not spec.loader:
            raise ImportError(f"Could not load seed script: {file_path}")

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Look for 'seed' async function
        if hasattr(module, "seed") and asyncio.iscoroutinefunction(module.seed):
            async with engine.begin() as conn:
                await module.seed(conn)
        else:
            logger.warning(
                "No async 'seed(connection)' function found in %s",
                file_path.name,
            )


class SeedFileRegistry:
    """Registry for seed file handlers."""

    def __init__(self) -> None:
        self._handlers: dict[str, SeedFileHandler] = {}

    @classmethod
    def _default_entries(cls) -> dict[str, SeedFileHandler]:
        """Declare the built-in seed file handlers."""
        return {
            ".sql": SQLSeedHandler(),
            ".py": PythonSeedHandler(),
        }

    @classmethod
    def with_defaults(cls) -> SeedFileRegistry:
        """Create a registry pre-populated with the built-in handlers."""
        registry = cls()
        for extension, handler in cls._default_entries().items():
            registry.register_handler(extension, handler)
        return registry

    def register_handler(self, extension: str, handler: SeedFileHandler) -> None:
        """Register a seed file handler."""
        self._handlers[extension] = handler

    async def execute_seed_file(self, file_path: Path, engine: Any) -> None:
        """Execute a seed file using the registered handler."""
        handler = self._handlers.get(file_path.suffix)
        if not handler:
            raise ValueError(f"Unsupported seed file type: {file_path.suffix}")
        await handler.execute(file_path, engine)


# Global seed file registry
_seed_file_registry = SeedFileRegistry.with_defaults()


class SeedManager:
    """Manages database seeding operations."""

    def __init__(self, connection_string: str, seeds_dir: str | Path = "seeds") -> None:
        self.connection_string = connection_string
        self.seeds_dir = Path(seeds_dir)
        self.engine = create_async_engine(connection_string)

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.close()

    async def initialize(self) -> None:
        """Initialize the seed tracking table."""
        async with self.engine.begin() as conn:
            is_sqlite = self.engine.dialect.name == "sqlite"
            val_type = "DATETIME" if is_sqlite else "TIMESTAMP WITH TIME ZONE"
            val_default = "CURRENT_TIMESTAMP" if is_sqlite else "NOW()"

            await conn.execute(
                text(
                    f"""
                    CREATE TABLE IF NOT EXISTS quadkit_seeds (
                        filename VARCHAR(255) PRIMARY KEY,
                        executed_at {val_type} DEFAULT {val_default},
                        hash VARCHAR(64)
                    );
                    """,
                ),
            )

    async def get_applied_seeds(self) -> set[str]:
        """Get list of already applied seeds."""
        async with self.engine.connect() as conn:
            # The tracking table is `quadkit_seeds` in every dialect (see
            # initialize()); the schema-qualified name would only resolve
            # on a PostgreSQL database with an `quadkit` schema.
            result = await conn.execute(text("SELECT filename FROM quadkit_seeds"))
            return {row[0] for row in result.fetchall()}

    async def run(self) -> None:
        """Run all pending seeds."""
        if not self.seeds_dir.exists():
            logger.warning("Seeds directory not found: %s", self.seeds_dir)
            return

        await self.initialize()
        applied = await self.get_applied_seeds()

        # Gather all valid seed files
        seed_files = [
            f
            for f in self.seeds_dir.iterdir()
            if f.is_file() and f.suffix in (".sql", ".py")
        ]

        # Sort by filename
        seed_files.sort(key=lambda x: x.name)

        for seed_file in seed_files:
            if seed_file.name in applied:
                logger.debug("Skipping applied seed: %s", seed_file.name)
                continue

            try:
                # Use the registry to execute the seed file
                await _seed_file_registry.execute_seed_file(seed_file, self.engine)

                # Record success
                async with self.engine.begin() as conn:
                    await conn.execute(
                        text(
                            "INSERT INTO quadkit_seeds (filename) VALUES (:filename)",
                        ),
                        {"filename": seed_file.name},
                    )
                logger.info("Successfully applied seed: %s", seed_file.name)

            except (DatabaseError, QueryError, RuntimeError):
                logger.exception("Failed to apply seed %s", seed_file.name)
                raise

    async def reset(self) -> None:
        """Clear seed history (does not truncate data tables)."""
        async with self.engine.begin() as conn:
            # DELETE (not TRUNCATE) so the reset works on every dialect —
            # SQLite has no TRUNCATE statement.
            await conn.execute(text("DELETE FROM quadkit_seeds"))

    async def close(self) -> None:
        """Dispose the engine and release its connection pool.

        Callers must invoke this (or use the seeder as an async context
        manager) when done, otherwise the pool's connections are leaked.
        """
        await self.engine.dispose()
