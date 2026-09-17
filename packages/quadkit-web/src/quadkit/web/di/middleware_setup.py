"""Middleware registration helper for the Quadkit web layer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from quadkit.contracts.core import HookRegistryProtocol
from quadkit.contracts.exceptions.container import UnresolvableDependencyError
from quadkit.contracts.exceptions.provider import ModuleVisibilityError
from quadkit.contracts.infra.cache import CacheBackendProtocol
from quadkit.logging import get_logger
from quadkit.primitives.context import Context
from quadkit.web.middleware.security import SecurityHeadersMiddleware

if TYPE_CHECKING:
    from starlette.applications import Starlette

    from quadkit.contracts.core.di import ContainerResolverProtocol
    from quadkit.web.config import WebConfig

logger = get_logger(__name__)

__all__ = ["MiddlewareSetup"]


class MiddlewareSetup:
    """Encapsulates Starlette middleware registration for the Quadkit web layer.

    Extracted from ``WebProvider`` to keep the provider focused on DI lifecycle
    (register/boot/shutdown) rather than application configuration details.

    Args:
        config: The web configuration driving middleware selection and ordering.
    """

    def __init__(
        self,
        config: WebConfig,
        hooks: HookRegistryProtocol | None = None,
    ) -> None:
        self._config = config
        self._hooks = hooks

    async def configure(
        self,
        app: Starlette,
        container: ContainerResolverProtocol,
    ) -> None:
        """Apply all configured middleware to the application.

        Middleware is applied in security-first order:

        1. Auto-configure CSP for API documentation (mutates ``self._config``).
        2. Security headers.
        3. CORS.
        4. CSRF (opt-in).
        5. Request context propagation.
        6. Request body size limit.
        7. Web hook emission middleware (outermost for broad coverage).

        The DI-scope layer is deliberately **not** added here: it is supplied
        exactly once by the native middleware stack built at Starlette
        construction (``DefaultMiddlewareStack`` via ``WebProvider``). Adding
        it here as well would execute it twice per request, creating two DI
        scopes and overwriting ``request.state.container``.

        Args:
            app: The Starlette application to configure.
            container: The resolved DI container; used for optional CSRF cache
                resolution.
        """
        await self._configure_csp()
        self._add_security_headers(app)
        self._add_docs_csp(app)
        self._add_host_validation(app)
        self._add_cors(app)
        await self._add_csrf(app, container)
        self._add_request_context(app, container)
        self._add_body_limit(app)
        self._add_hooks(app)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _configure_csp(self) -> None:
        """Auto-configure CSP directives for API documentation if enabled."""
        api_docs = getattr(self._config, "api_docs", None)
        if not api_docs or not api_docs.enabled:
            return

        # plans/09172026 H-03: state which docs asset mode is active. The
        # default is "local" (vendored assets served by the app, no
        # third-party requests); "cdn" / "custom" are explicit opt-ins.
        logger.info(
            "api_docs_assets_mode",
            mode=api_docs.assets_mode(
                swagger_js_url=getattr(self._config, "swagger_js_url", None),
                swagger_css_url=getattr(self._config, "swagger_css_url", None),
                redoc_js_url=getattr(self._config, "redoc_js_url", None),
            ),
            cdn_base=getattr(api_docs, "cdn_base", None),
        )

        # Docs enabled implies security headers on: the default security
        # config carries the strict CSP that covers the vendored assets.
        # (This also held before H-03 — the merge below used to be the only
        # place the default SecurityConfig was materialised.)
        if not hasattr(self._config, "security") or not self._config.security:
            from quadkit.web.security.config import SecurityConfig

            self._config.security = SecurityConfig()

        required_domains = api_docs.get_required_domains()
        if not required_domains:
            return

        csp = self._config.security.csp
        directives = csp.directives if hasattr(csp, "directives") else {}
        for directive, domains in required_domains.items():
            if directive not in directives:
                directives[directive] = set()
            current = directives[directive]
            if isinstance(current, str):
                current_set = {current}
            elif not isinstance(current, set):
                current_set = set(current) if current else set()
            else:
                current_set = current

            current_set.update(domains)
            directives[directive] = current_set

        logger.info(
            "auto_configured_csp_for_api_docs",
            directives={
                k: list(v) if isinstance(v, set) else v for k, v in directives.items()
            },
        )

    def _add_docs_csp(self, app: Starlette) -> None:
        """Serve the docs pages under a strict route-scoped CSP (H-03).

        Applies only to the docs HTML pages and their vendored assets; every
        other route keeps the application's own policy untouched.
        """
        api_docs = getattr(self._config, "api_docs", None)
        if not api_docs or not api_docs.enabled:
            return

        docs_paths = [
            p
            for p in (
                getattr(self._config, "swagger_ui_url", None),
                getattr(self._config, "redoc_url", None),
                "/docs-static",
            )
            if p
        ]
        if not docs_paths:
            return

        from quadkit.web.middleware.security import DocsCSPMiddleware
        from quadkit.web.security.config.csp import CSPConfig

        directives: dict[str, Any] = dict(CSPConfig().directives)
        for directive, domains in api_docs.get_required_domains().items():
            merged = set(directives.get(directive, set())) | set(domains)
            directives[directive] = merged

        policy = CSPConfig(enabled=True, directives=directives).build_header()
        app.add_middleware(
            DocsCSPMiddleware,
            docs_paths=tuple(docs_paths),
            policy=policy,
        )
        logger.info(
            "docs_csp_applied",
            paths=docs_paths,
            policy=policy,
        )

    def _add_security_headers(self, app: Starlette) -> None:
        """Add security headers middleware when a security config is present."""
        if hasattr(self._config, "security") and self._config.security:
            if not getattr(self._config.security, "enabled", True):
                return
            self._warn_on_weak_csp(self._config.security)
            app.add_middleware(
                SecurityHeadersMiddleware,
                config=self._config.security,
                enabled=True,
            )

    @staticmethod
    def _warn_on_weak_csp(security_config: Any) -> None:
        """Warn when an enabled CSP still allows inline/eval scripts.

        The framework's default CSP directives include ``'unsafe-inline'``
        and ``'unsafe-eval'`` (required by the bundled API docs).  Those
        directives neutralise most of CSP's XSS protection, so operators
        who explicitly enable CSP deserve a loud nudge to tighten them.
        """
        csp = getattr(security_config, "csp", None)
        if csp is None or not getattr(csp, "enabled", False):
            return
        directives = getattr(csp, "directives", None) or {}
        weak: list[str] = []
        for name in ("script-src", "script-src-elem"):
            value = directives.get(name)
            if isinstance(value, (set, list)):
                text = " ".join(str(v) for v in value)
            else:
                text = str(value or "")
            if "'unsafe-inline'" in text or "'unsafe-eval'" in text:
                weak.append(name)
        if weak:
            logger.warning(
                "csp_weak_directives",
                directives=weak,
                hint=(
                    "CSP is enabled but still allows 'unsafe-inline'/"
                    "'unsafe-eval'; tighten directives to gain real XSS "
                    "protection"
                ),
            )

    def _add_host_validation(self, app: Starlette) -> None:
        """Add host-header validation when an allowed_hosts allowlist is set."""
        if not hasattr(self._config, "security") or not self._config.security:
            return
        allowed_hosts = list(getattr(self._config.security, "allowed_hosts", []))
        if not allowed_hosts:
            return

        from quadkit.web.middleware.host import HostValidationMiddleware

        app.add_middleware(HostValidationMiddleware, allowed_hosts=allowed_hosts)

    def _add_cors(self, app: Starlette) -> None:
        """Add CORS middleware when CORS is enabled in config."""
        if not self._config.cors.enabled:
            return

        from quadkit.logging.debug import is_debug_mode
        from quadkit.web.security.config import CORSConfig
        from quadkit.web.security.cors.middleware import (
            CORSMiddleware as WebCORSMiddleware,
        )

        cors_cfg = self._config.cors
        _debug_active = is_debug_mode() or self._config.server.debug
        allowed_origins = cors_cfg.allow_origins
        if cors_cfg.debug_permissive and _debug_active:
            allowed_origins = ["*"]
            logger.warning(
                "cors.debug_permissive",
                reason="debug_permissive=True and debug mode active — using wildcard CORS origins",
            )

        web_cors_config = CORSConfig(
            allowed_origins=allowed_origins,
            allow_credentials=cors_cfg.allow_credentials,
            allow_methods=cors_cfg.allow_methods,
            allow_headers=cors_cfg.allow_headers,
            expose_headers=cors_cfg.expose_headers,
            max_age=cors_cfg.max_age,
        )
        app.add_middleware(WebCORSMiddleware, config=web_cors_config)

    async def _add_csrf(
        self,
        app: Starlette,
        container: ContainerResolverProtocol,
    ) -> None:
        """Add CSRF protection middleware when opt-in config is present."""
        security_cfg = getattr(self._config, "security", None)
        if security_cfg is None:
            return
        if not getattr(security_cfg, "enabled", True):
            return
        if not getattr(security_cfg, "enable_csrf", True):
            return
        csrf_cfg = getattr(security_cfg, "csrf", None)
        if csrf_cfg is None or not csrf_cfg.enabled:
            return

        from quadkit.web.security.csrf.middleware import CSRFProtectionMiddleware

        csrf_cache = None
        try:
            csrf_cache = cast("Any", container).resolve_sync(CacheBackendProtocol)
        except (
            UnresolvableDependencyError,
            AttributeError,
            RuntimeError,
            ModuleVisibilityError,
        ):
            pass

        app.add_middleware(
            CSRFProtectionMiddleware,
            config=csrf_cfg,
            cache=csrf_cache,
        )

    def _add_request_context(
        self,
        app: Starlette,
        container: ContainerResolverProtocol,
    ) -> None:
        """Add request context middleware wired to the shared core context."""
        from quadkit.web.middleware.request_context import RequestContextMiddleware

        context = cast("Any", container).resolve_sync(Context)
        app.add_middleware(RequestContextMiddleware, context=context)

    def _add_hooks(self, app: Starlette) -> None:
        """Add outermost web hook middleware for request/response events."""
        from quadkit.web.middleware.hooks import WebHooksMiddleware

        app.add_middleware(WebHooksMiddleware, hooks=self._hooks)

    def _add_body_limit(self, app: Starlette) -> None:
        """Add request body size limit middleware when configured.

        Added before the hook middleware so oversized requests are still
        rejected near the edge while hooks can observe the prepared response.
        """
        max_body_size = getattr(self._config, "max_body_size", None)
        if max_body_size is None:
            return

        from quadkit.web.middleware.body_limit import RequestBodySizeLimitMiddleware

        app.add_middleware(
            RequestBodySizeLimitMiddleware,
            max_body_size=max_body_size,
        )
