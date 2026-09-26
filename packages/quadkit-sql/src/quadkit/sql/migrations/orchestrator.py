"""Migration orchestrator for high-level programmatic operations.

**Boot ordering contract**

The orchestrator must be invoked between the ``register`` and ``boot``
phases of the provider lifecycle so that all database providers have
registered their connection pools before migrations run, and application
providers that depend on schema state are only booted after migrations
have completed:

1. All providers call ``register()`` — connection pools are set up.
2. ``MigrationOrchestrator.run_migrations()`` (or ``run_pending()``) is
   called — schema is brought to the desired state.
3. All providers call ``boot()`` — application code may now assume the
   schema is current.

Violating this order (e.g. booting a provider that seeds reference data
before migrations run) will cause schema-mismatch errors at startup.
"""

from __future__ import annotations

from collections import deque
from pathlib import Path
from typing import Any

from quadkit.logging import get_logger
from quadkit.sql.lib import infer_provider_type_from_url

logger = get_logger(__name__)


class MigrationOrchestrator:
    """Orchestrator for managing multi-package migrations."""

    def __init__(
        self,
        provider: Any,
        database_url: str | None = None,
        base_path: Path | str | None = None,
        packages_dir: Path | str | None = None,
    ) -> None:
        """Initialize orchestrator.

        Args:
            provider: Database provider or first positional arg if legacy call.
            database_url: Connection string or second positional arg.
            base_path: Optional base path for local migrations discovery (defaults to cwd).
            packages_dir: Optional path to packages directory (defaults to base_path/packages).
        """
        # Handle cases where it might be called as MigrationOrchestrator(url) or (provider, url)
        if isinstance(provider, str) and database_url is None:
            self.provider = None
            self.database_url = provider
        else:
            self.provider = provider
            self.database_url = database_url  # type: ignore[assignment]

        self.connection_string = self.database_url  # Compatibility

        # Ensure base_path is a Path object
        if base_path is None:
            self.base_path = Path.cwd()
        else:
            self.base_path = Path(base_path)

        # Determine package root
        if packages_dir:
            self.package_root = Path(packages_dir)
        else:
            # Try to find a 'packages' directory up the tree
            self.package_root = self.base_path / "packages"
            curr = self.base_path
            found = False
            for _ in range(3):
                if (curr / "packages").exists():
                    self.package_root = curr / "packages"
                    found = True
                    break
                curr = curr.parent

            if not found:
                # Last resort fallback to base_path/packages
                self.package_root = self.base_path / "packages"

    async def initialize_migration_table(self) -> None:
        """Ensure migration tracking table exists."""
        if (
            self.database_url
            and infer_provider_type_from_url(str(self.database_url)) == "sqlite"
        ):
            import aiosqlite

            path = self.database_url.split("///")[-1].split("://")[-1]
            if path == ":memory:":
                return
            async with aiosqlite.connect(path) as conn:
                await conn.execute(
                    "CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY, name TEXT NOT NULL, applied_at TEXT NOT NULL, success BOOLEAN NOT NULL, error_message TEXT)",
                )
                await conn.commit()

    def discover_packages(self) -> list[dict[str, Any]]:
        """Find all packages with migration manifests, including the local app.

        Returns a list of package metadata dicts containing `package`, `path`, and
        optional `dependencies` entries.
        """
        try:
            import yaml
        except ImportError as exc:
            msg = (
                "pyyaml is required for migration orchestration. "
                "Install it with: pip install pyyaml"
            )
            raise ImportError(msg) from exc

        packages: list[dict[str, Any]] = []

        # 1. Discover From Local Path (Current Application)
        local_manifest = self.base_path / "migrations" / "manifest.yaml"
        if local_manifest.exists():
            try:
                with local_manifest.open() as f:
                    manifest = yaml.safe_load(f)
                    manifest["path"] = local_manifest.parent
                    packages.append(manifest)
            except Exception:  # noqa: BLE001 — a broken local manifest must not abort migration discovery
                logger.exception("Failed to load local manifest: %s", local_manifest)
        elif (self.base_path / "migrations").exists():
            # If no manifest but migrations dir exists, treat as a generic package
            packages.append(
                {
                    "package": "app",
                    "path": self.base_path / "migrations",
                    "dependencies": [
                        "the optional provider",
                        "quadkit-events",
                        "quadkit-tasks",
                    ],
                },
            )

        # 2. Discover From Packages Directory
        if self.package_root.exists():
            for manifest_path in self.package_root.glob("*/migrations/manifest.yaml"):
                try:
                    # Avoid double-adding if base_path is inside package_root
                    if manifest_path.parent == (self.base_path / "migrations"):
                        continue

                    with manifest_path.open() as f:
                        manifest = yaml.safe_load(f)
                        manifest["path"] = manifest_path.parent
                        packages.append(manifest)
                except Exception:  # noqa: BLE001 — one broken manifest must not abort discovery of the remaining packages
                    logger.exception("Failed to load manifest: %s", manifest_path)
        else:
            logger.debug(
                "Package root %s not found; skipping framework discovery.",
                self.package_root,
            )

        return packages

    def resolve_dependencies(
        self,
        packages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Topologically sort packages based on dependencies."""

        # Build graph
        graph = {p["package"]: p for p in packages}
        adj: dict[str, list[str]] = {p["package"]: [] for p in packages}
        in_degree = {p["package"]: 0 for p in packages}

        for p in packages:
            deps = p.get("dependencies", [])
            if isinstance(deps, str) and deps.lower() == "none":
                deps = []

            for dep in deps:
                if dep in graph:
                    adj[dep].append(p["package"])
                    in_degree[p["package"]] += 1
                else:
                    logger.debug(
                        "Dependency %s for %s not found in discovered packages.",
                        dep,
                        p["package"],
                    )

        # Kahn's algorithm
        # Seed queue with nodes that have zero in-degree
        queue = deque([name for name, deg in in_degree.items() if deg == 0])
        sorted_packages = []

        while queue:
            u = queue.popleft()
            sorted_packages.append(graph[u])
            for v in adj[u]:
                in_degree[v] -= 1
                if in_degree[v] == 0:
                    queue.append(v)

        if len(sorted_packages) != len(packages):
            raise RuntimeError(
                "Circular dependency detected in migrations or missing dependencies.",
            )

        return sorted_packages

    async def run_migrations(self, target: str = "head") -> None:
        """Run migrations across all discovered packages in order."""
        from quadkit.sql.migrations.manager import (
            AlembicManager,
        )

        packages = self.discover_packages()
        sorted_packages = self.resolve_dependencies(packages)

        for pkg in sorted_packages:
            logger.info("Migrating package: %s...", pkg["package"])
            version_table = f"alembic_{pkg['package'].replace('-', '_')}"
            manager = AlembicManager(
                connection_or_provider=self.database_url,
                migrations_path=pkg["path"],
                alembic_config={"version_table": version_table},
            )
            # Ensure the versions directory is set correctly relative to the package migrations path
            await manager.upgrade(target)
            logger.info(
                "Successfully migrated %s using version table %s.",
                pkg["package"],
                version_table,
            )
