"""Conformance tests that enforce canonical Provider method signatures.

These tests act as a monorepo-wide guardrail: if any provider in any
``quadkit-*/src/`` tree defines ``shutdown``, ``register``, or
``from_config`` with the wrong signature, the corresponding test fails and
reports **all** violators at once — not just the first one.

Phase 8 of the DX improvement standardised:

* ``shutdown(self) -> None``       — zero extra parameters.
* ``register(self, container: ContainerRegistrarProtocol) -> None``
  — exactly one extra parameter named ``container``.
* ``from_config(cls, config, **context) -> Self``
  — at least a ``config`` positional arg and a ``**context`` VAR_KEYWORD arg.
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from quadkit.di.provider import Provider

if TYPE_CHECKING:
    pass

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

#: Absolute path to the repository root (four levels above this file).
#: ``quadkit/tests/unit/di/`` → ``quadkit/tests/unit/`` → ``quadkit/tests/``
#: → ``quadkit/`` → ``<repo-root>``
_REPO_ROOT: Path = Path(__file__).parents[4]


# ---------------------------------------------------------------------------
# Discovery helpers
# ---------------------------------------------------------------------------


def _src_paths() -> list[Path]:
    """Return all ``quadkit-*/src`` and ``quadkit/src`` directories.

    Returns:
        Sorted list of existing source-tree root directories that belong to
        Quadkit extension packages plus the core ``quadkit`` package.
    """
    paths: list[Path] = sorted(_REPO_ROOT.glob("quadkit-*/src"))
    core_src = _REPO_ROOT / "quadkit" / "src"
    if core_src.is_dir():
        paths.append(core_src)
    return [p for p in paths if p.is_dir()]


def _discover_providers() -> list[type[Provider]]:
    """Walk every package source tree and collect all ``Provider`` subclasses.

    Uses :func:`pkgutil.walk_packages` so that each ``quadkit-*`` namespace
    is scanned independently.  Import errors (e.g. optional heavy extras not
    installed in CI) are silently skipped; the class must be *defined* in the
    scanned module (``obj.__module__ == module.__name__``) to avoid counting
    re-imports as duplicates.

    Returns:
        Deduplicated list of concrete ``Provider`` subclasses found across the
        entire monorepo, in discovery order.
    """
    seen: set[int] = set()
    found: list[type[Provider]] = []

    for src_path in _src_paths():
        for _importer, module_name, _is_pkg in pkgutil.walk_packages(
            path=[str(src_path)],
            onerror=lambda _name: None,
        ):
            try:
                module = importlib.import_module(module_name)
            except Exception:  # noqa: BLE001 — skip modules with missing extras
                continue

            # Use vars() instead of inspect.getmembers to avoid triggering
            # lazy __getattr__ loaders on namespace-package __init__ modules.
            for obj in vars(module).values():
                if (
                    isinstance(obj, type)
                    and id(obj) not in seen
                    and obj is not Provider
                    and issubclass(obj, Provider)
                    and obj.__module__ == module.__name__
                ):
                    seen.add(id(obj))
                    found.append(obj)

    return found


def _defines_method(cls: type, method_name: str) -> bool:
    """Return ``True`` only when *cls* itself introduces *method_name*.

    Checking ``cls.__dict__`` instead of ``hasattr`` ensures that inherited
    methods (e.g. the no-op stubs on the base ``Provider``) are not reported
    as violations.

    Args:
        cls: The class to inspect.
        method_name: Name of the method to look for.

    Returns:
        ``True`` if the method is present in the class's own ``__dict__``.
    """
    return method_name in cls.__dict__


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------


class TestProviderConformance:
    """Conformance suite for canonical ``Provider`` method signatures.

    All three tests share a single provider-discovery pass via the
    ``all_providers`` class-scoped fixture, so the filesystem walk runs only
    once per test session.
    """

    @pytest.fixture(scope="class")
    def all_providers(self) -> list[type[Provider]]:
        """Discover every ``Provider`` subclass across the monorepo.

        Returns:
            Deduplicated list of ``Provider`` subclasses, ready for signature
            inspection.
        """
        return _discover_providers()

    # ------------------------------------------------------------------
    # shutdown
    # ------------------------------------------------------------------

    def test_shutdown_signature(
        self,
        all_providers: list[type[Provider]],
    ) -> None:
        """``shutdown`` must accept no parameters other than ``self``.

        Canonical signature::

            async def shutdown(self) -> None: ...

        Any extra positional, keyword, or variadic parameter is a violation.

        Args:
            all_providers: Injected fixture supplying all discovered providers.
        """
        violators: list[str] = []

        for cls in all_providers:
            if not _defines_method(cls, "shutdown"):
                continue

            sig = inspect.signature(cls.shutdown)
            extra = [
                name
                for name, _param in sig.parameters.items()
                if name != "self"
            ]

            if extra:
                violators.append(
                    f"{cls.__module__}.{cls.__qualname__}.shutdown"
                    f" — unexpected parameter(s): {extra!r}"
                )

        assert not violators, (
            f"{len(violators)} provider(s) define shutdown() with non-canonical"
            f" signatures:\n" + "\n".join(f"  • {v}" for v in sorted(violators))
        )

    # ------------------------------------------------------------------
    # register
    # ------------------------------------------------------------------

    def test_register_signature(
        self,
        all_providers: list[type[Provider]],
    ) -> None:
        """``register`` must accept exactly one extra parameter named ``container``.

        Canonical signature::

            async def register(self, container: ContainerRegistrarProtocol) -> None: ...

        Args:
            all_providers: Injected fixture supplying all discovered providers.
        """
        violators: list[str] = []

        for cls in all_providers:
            if not _defines_method(cls, "register"):
                continue

            sig = inspect.signature(cls.register)
            extra_params = [
                name
                for name in sig.parameters
                if name != "self"
            ]

            if extra_params != ["container"]:
                violators.append(
                    f"{cls.__module__}.{cls.__qualname__}.register"
                    f" — expected ['container'], got {extra_params!r}"
                )

        assert not violators, (
            f"{len(violators)} provider(s) define register() with non-canonical"
            f" signatures:\n" + "\n".join(f"  • {v}" for v in sorted(violators))
        )

    # ------------------------------------------------------------------
    # from_config
    # ------------------------------------------------------------------

    def test_from_config_signature(
        self,
        all_providers: list[type[Provider]],
    ) -> None:
        """``from_config`` must follow the ``(cls, config, **context)`` pattern.

        Canonical signature (``cls`` is automatically bound for class-methods
        and therefore absent from :func:`inspect.signature` output)::

            @classmethod
            def from_config(cls, config: SomeConfig, **context: Any) -> Self: ...

        Requirements checked:

        * At least one parameter is present after stripping ``cls``/``self``.
        * The **first** parameter is named ``config`` and is positional.
        * At least one parameter has ``VAR_KEYWORD`` kind (the ``**context``).

        Args:
            all_providers: Injected fixture supplying all discovered providers.
        """
        violators: list[str] = []

        for cls in all_providers:
            if not _defines_method(cls, "from_config"):
                continue

            sig = inspect.signature(cls.from_config)
            # For a @classmethod, `cls` is already bound → not in sig.parameters.
            # GuardProtocol against the edge-case where someone wrote a plain method.
            params = [
                p
                for p in sig.parameters.values()
                if p.name not in ("cls", "self")
            ]

            positional_kinds = (
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                inspect.Parameter.POSITIONAL_ONLY,
            )

            has_config_first = bool(
                params
                and params[0].name == "config"
                and params[0].kind in positional_kinds
            )
            has_var_keyword = any(
                p.kind == inspect.Parameter.VAR_KEYWORD for p in params
            )

            if not (has_config_first and has_var_keyword):
                raw = [p.name for p in sig.parameters.values()]
                violators.append(
                    f"{cls.__module__}.{cls.__qualname__}.from_config"
                    f" — expected (cls, config, **context), got params {raw!r}"
                )

        assert not violators, (
            f"{len(violators)} provider(s) define from_config() with non-canonical"
            f" signatures:\n" + "\n".join(f"  • {v}" for v in sorted(violators))
        )
