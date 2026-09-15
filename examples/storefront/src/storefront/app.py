"""Convention followed: **Composition root** — one file knows how modules and
controllers fit; ``create_app(config=...)`` is the injection seam.

Composition root for the storefront demo — start reading here.

This is the framework's **multi-module** demo (Pattern 3, "Modular App
Layout" — see ``docs/getting-started/project-structure.md``). Every other
demo in ``examples/`` is one flat package with one ``Provider``; this one
composes two bounded contexts, each its own ``@module``, under
``storefront/modules/``:

    storefront/modules/
        catalog/   — owns product data + pricing; exports ProductCatalogProtocol
        orders/    — places orders; imports CatalogModule, resolves the protocol

``storefront.modules.build_modules()`` returns both configured modules in
dependency order. The only line that makes ``orders`` able to see the
catalog's protocol is ``OrdersModule.configure(catalog=...)`` importing
that same ``CatalogModule.configure()`` instance — see
``storefront/modules/orders/__init__.py``.

Controllers are *not* listed by hand here: ``WebModule.configure(discover=
[...])`` walks both module packages and finds every ``Controller``
subclass automatically, so adding a third bounded context never touches
this file.

Run with::

    PYTHONPATH=src uv run python -m storefront
"""

from __future__ import annotations

from quadkit.app.base import Application
from quadkit.config.main import QuadkitConfig
from quadkit.web.module import WebModule
from storefront.modules import build_modules as build_bounded_contexts
from storefront.ui.pages import StorefrontPageController


def build_modules() -> list[object]:
    """Declarative capabilities: the two bounded contexts, plus the web layer.

    ``WebModule.configure(discover=[...])`` scans
    ``storefront.modules.catalog`` and ``storefront.modules.orders`` for
    ``Controller`` subclasses instead of listing them by hand — the
    per-module ``controllers.py`` files stay self-contained.
    """
    return [
        *build_bounded_contexts(),
        WebModule.configure(
            controllers=[StorefrontPageController],
            discover=[
                "storefront.modules.catalog",
                "storefront.modules.orders",
            ],
        ),
    ]


def create_app(config: QuadkitConfig | None = None) -> Application:
    """Create the application in ``CREATED`` state (not yet started).

    Accepts an optional ``QuadkitConfig`` for scenarios where the config
    is loaded explicitly (e.g. hub mounting). When called standalone, the
    framework auto-discovers ``application.yaml`` from the working
    directory.

    Args:
        config: Optional pre-loaded config. When ``None`` the framework
            auto-discovers ``application.yaml`` from the working directory.
    """
    app = Application(name="storefront", config=config)
    app.add_modules(build_modules())
    return app


__all__ = ["build_modules", "create_app"]
