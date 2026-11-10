"""Namespace primitive — keep ``quadkit``'s search path current.

``quadkit/__init__.py`` extends the package path once, at first import, so every
``quadkit-*`` distribution installed before the process started is visible. A
distribution installed *afterwards* — a plugin, a fixture pack — is not, and its
``quadkit.*`` submodules stay invisible until the path is recomputed.

Recomputing rather than extending also drops portions whose ``sys.path`` entry is
gone, so an uninstalled tree stops shadowing a fresh install of the same
distribution.
"""

from __future__ import annotations

import importlib
import pkgutil

__all__ = ["refresh_namespace"]


def refresh_namespace() -> None:
    """Recompute the ``quadkit`` search path from the current ``sys.path``.

    Mutated in place: children such as ``the optional provider module`` hold a reference to the
    same list and notice the change. Idempotent; call it after a path entry
    gains a tree.
    """
    package = importlib.import_module("quadkit")
    base = package.__path__[0]
    found = pkgutil.extend_path([base], package.__name__)
    package.__path__[:] = list(dict.fromkeys(found))
    importlib.invalidate_caches()
