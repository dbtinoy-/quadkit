"""Convenience async API wrappers for SeedManager."""

from __future__ import annotations

from typing import TYPE_CHECKING

from quadkit.sql.seeds.manager import SeedManager

if TYPE_CHECKING:
    from pathlib import Path


async def run_seeds(connection_string: str, seeds_path: str | Path = "seeds") -> None:
    """Run all pending seeds."""
    manager = SeedManager(connection_string, seeds_path)
    await manager.run()


async def reset_seeds(connection_string: str) -> None:
    """Reset seed history (does not truncate actual data tables)."""
    manager = SeedManager(connection_string)
    # We might not know seeds path for reset, but manager needs init args.
    # It only matters if we call run().
    await manager.reset()
