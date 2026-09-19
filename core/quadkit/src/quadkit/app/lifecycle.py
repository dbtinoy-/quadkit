"""Application lifecycle collaborator.

Extracts boot and shutdown orchestration from Application into a
testable, independently-verifiable collaborator.
"""

from __future__ import annotations

import sys
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from quadkit.config import QuadkitConfig
    from quadkit.di.container import Container
    from quadkit.di.orchestrator import ProviderOrchestrator
    from quadkit.logging import LoggerProtocol


class ApplicationLifecycle:
    """Manages application boot and shutdown sequences.

    Extracted from Application to isolate lifecycle orchestration
    for testability and single-responsibility.
    """

    def __init__(
        self,
        container: Container,
        orchestrator: ProviderOrchestrator,
        config: QuadkitConfig,
        logger: LoggerProtocol,
        app_name: str,
    ) -> None:
        self._container = container
        self._orchestrator = orchestrator
        self._config = config
        self._logger = logger
        self._app_name = app_name
        self._start_time: float | None = None
        self._uptime_seconds: float | None = None

    async def boot(
        self,
        *,
        auto_discover: bool = False,
        discover_callback: Any | None = None,
        modules: list[type | Any] | None = None,
        validate_secrets_callback: Any | None = None,
    ) -> None:
        """Execute the boot sequence.

        Args:
            auto_discover: Whether to run auto-discovery.
            discover_callback: Callback to invoke for auto-discovery.
            modules: List of registered modules.
            validate_secrets_callback: Callback to invoke for secrets validation.
        """
        self._start_time = time.monotonic()
        self._logger.info("application.starting", name=self._app_name)

        if discover_callback is not None:
            # The callback itself guards auto-discovery on the app config;
            # it must always run so explicitly-added modules are compiled.
            discover_callback()

        if validate_secrets_callback is not None:
            validate_secrets_callback()

        await self._orchestrator.boot_all(self._container)

        self._logger.info("application.started", name=self._app_name)

    async def shutdown(self) -> None:
        """Execute the shutdown sequence."""
        self._logger.info("application.stopping", name=self._app_name)

        try:
            await self._orchestrator.shutdown()
            await self._container.dispose()
        finally:
            if self._start_time is not None:
                self._uptime_seconds = time.monotonic() - self._start_time
            else:
                self._uptime_seconds = 0.0

            self._logger.info(
                "application.stopped",
                name=self._app_name,
                uptime_seconds=round(self._uptime_seconds, 3),
            )

    def print_banner(
        self,
        provider_count: int,
        module_count: int,
    ) -> None:
        """Print a diagnostic startup banner when enabled.

        Args:
            provider_count: Number of registered providers.
            module_count: Number of registered modules.
        """
        import os

        if os.environ.get("QK_QUIET", "").strip() in ("1", "true", "yes"):
            return
        show = getattr(self._config, "get", lambda _key, default: default)(
            "app.show_banner", True
        )
        if not show:
            return

        try:
            from importlib.metadata import PackageNotFoundError
            from importlib.metadata import version as pkg_version

            lx_version = pkg_version("quadkit")
        except (ImportError, PackageNotFoundError):
            lx_version = "dev"

        py_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        width = 60
        sep = "═" * (width - 2)

        lines = [
            f"╔{sep}╗",
            f"║  Quadkit {lx_version:<{width - 14}}║",
            f"║  Python {py_version} {'':>{width - 17}}║",
            "║" + " " * (width - 2) + "║",
            f"║  Providers : {provider_count:<{width - 16}}║",
            f"║  Modules   : {module_count:<{width - 16}}║",
            f"╚{sep}╝",
        ]
        banner_text = "\n".join(lines)
        self._logger.info("application.startup_banner", banner=banner_text)


__all__ = ["ApplicationLifecycle"]
