"""Fleet: boot every demo Application in-process and mount it on the hub.

Each child is a complete Quadkit ``Application`` (own DI container, own
providers) whose Starlette app is mounted under ``/examples/<slug>/``. Demos
keep working standalone — embedding simply reuses their module factories.
"""

from __future__ import annotations

import importlib
from pathlib import Path
import sys
from typing import TYPE_CHECKING

from starlette.applications import Starlette

from example_hub.services.registry import ServiceRegistry
from example_hub.subsite import SubsiteMiddleware
from quadkit.config.main import QuadkitConfig
from quadkit.logging import get_logger
from quadkit.web.di.provider import WebProvider

if TYPE_CHECKING:
    from quadkit.app import Application

logger = get_logger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[4]


class Fleet:
    """Boot, mount and track the embedded demo applications."""

    def __init__(self, registry: ServiceRegistry) -> None:
        self._registry = registry
        self._apps: dict[str, Application] = {}
        self._failures: dict[str, str] = {}

    @property
    def mounted(self) -> dict[str, bool]:
        """Slug → whether the demo booted and is serving."""
        return dict.fromkeys(self._apps, True)

    @property
    def failures(self) -> dict[str, str]:
        """Slug → error text for demos that failed to boot."""
        return dict(self._failures)

    def snapshot(self) -> list[dict[str, object]]:
        """Status payload for ``/api/status`` (see ServiceRegistry.snapshot)."""
        return self._registry.snapshot(self.mounted, self.failures)

    def _ensure_import_paths(self) -> None:
        for svc in self._registry.web_services():
            src = REPO_ROOT / "examples" / svc.demo_dir / "src"
            if not src.is_dir():
                raise FileNotFoundError(f"missing demo sources: {src}")
            if str(src) not in sys.path:
                sys.path.append(str(src))

    def _load_child_config(self, svc: ServiceRegistry.DemoService) -> QuadkitConfig:
        """Load the child demo's own ``application.yaml``.

        When the hub mounts a child, cwd is the hub's directory, so the
        framework's auto-discovery would load the hub's config instead of
        the child's.  This method loads the child's YAML explicitly and
        passes it to ``create_app(config=…)``.
        """
        yaml_path = REPO_ROOT / "examples" / svc.demo_dir / "application.yaml"
        if yaml_path.exists():
            return QuadkitConfig.from_yaml(yaml_path)
        return QuadkitConfig()

    async def mount_all(self, parent: Starlette) -> None:
        """Boot every web demo and mount it under ``/examples/<slug>/``.

        A failing demo is logged and surfaced via :attr:`failures`; it never
        prevents the remaining demos or the hub itself from serving.
        """
        self._ensure_import_paths()
        for svc in self._registry.web_services():
            child_app: Application | None = None
            try:
                module = importlib.import_module(svc.app_path)
                child_config = self._load_child_config(svc)
                child_app = module.create_app(config=child_config)
                await child_app.start()
                web = await child_app.container.resolve(WebProvider)
                if web.starlette is None:
                    raise RuntimeError("child starlette app missing")
                base = f"/examples/{svc.slug}"
                parent.mount(
                    base,
                    app=SubsiteMiddleware(web.starlette, base=base),
                )
                self._apps[svc.slug] = child_app
                logger.info("fleet_child_mounted", slug=svc.slug)
            except Exception as exc:  # noqa: BLE001 - isolate child faults
                if child_app is not None and self._apps.get(svc.slug) is not child_app:
                    try:
                        await child_app.stop()
                    except Exception as cleanup_exc:  # noqa: BLE001
                        logger.warning(
                            "fleet_child_cleanup_failed",
                            slug=svc.slug,
                            error=str(cleanup_exc),
                        )
                self._failures[svc.slug] = f"{type(exc).__name__}: {exc}"
                logger.error("fleet_child_failed", slug=svc.slug, error=str(exc))

    async def aclose(self) -> None:
        """Shut down every booted child application."""
        for slug, app in reversed(list(self._apps.items())):
            try:
                await app.stop()
            except Exception as exc:  # noqa: BLE001 - best-effort teardown
                logger.warning("fleet_child_shutdown_failed", slug=slug, error=str(exc))
        self._apps.clear()


__all__ = ["Fleet"]
