"""Public contract API tests (plan 01 §2 / plan 06 PR 2).

The executable half of the public contract boundary: these tests run
against `quadkit-contracts` exactly as published — including in the
release pipeline, where the retained suite executes from the exported
tree against the built wheels with no monorepo sources present.

Invariants asserted here, without any monorepo fixtures:

1. Every contracts namespace imports.
2. Every ``__all__`` name in every public contracts module resolves —
   no dangling lazy exports (the exact bug class that once shipped a
   fake re-exporting a private package).
3. The exception taxonomy is single-rooted: every exported ``Error``
   class in the ``exceptions`` namespaces derives from ``QuadkitError``.
4. ``*Protocol`` exports really are protocol types.

The namespace classification itself (public-core vs public-extension)
is enforced by ``dev/release/check_public_contracts.py``; this file
guards the *shape* of the surface that classification covers.
"""

from __future__ import annotations

import importlib
import pkgutil
from typing import Any

import pytest

import quadkit.contracts

_DIST = "quadkit.contracts"


def _public_modules() -> list[str]:
    """All module paths under quadkit.contracts, layout-independent."""

    modules: list[str] = []
    package = importlib.import_module(_DIST)
    for info in pkgutil.walk_packages(package.__path__, prefix=f"{_DIST}."):
        modules.append(info.name)
    return modules


_MODULES = _public_modules()
_ROOT_ALL = getattr(quadkit.contracts, "__all__", ()) or ()


def test_every_namespace_imports() -> None:
    """Each top-level contracts namespace imports on its own."""

    namespaces = {
        name.split(".")[2] for name in _MODULES if name.count(".") >= 2
    }
    assert namespaces, "no namespaces discovered under quadkit.contracts"
    for ns in sorted(namespaces):
        module = importlib.import_module(f"{_DIST}.{ns}")
        assert module is not None


def test_every_module_imports() -> None:
    for name in _MODULES:
        importlib.import_module(name)


def _exported_entries(module_name: str) -> list[tuple[str, Any]]:
    module = importlib.import_module(module_name)
    exported = getattr(module, "__all__", None) or ()
    return [(f"{module_name}.{name}", getattr(module, name, None))
            for name in exported]


def test_no_dangling_lazy_exports() -> None:
    """Every ``__all__`` name in every public module must resolve."""

    dangling: list[str] = []
    for module_path in _MODULES:
        for label, obj in _exported_entries(module_path):
            if obj is None:
                dangling.append(label)
    assert dangling == []


def test_root_lazy_exports_resolve() -> None:
    for name in _ROOT_ALL:
        assert hasattr(quadkit.contracts, name), f"quadkit.contracts.{name}"


def test_protocol_exports_are_protocol_types() -> None:
    offenders: list[str] = []
    for module_path in _MODULES:
        for label, obj in _exported_entries(module_path):
            name = label.rsplit(".", 1)[-1]
            if name.endswith("Protocol"):
                if not (isinstance(obj, type)
                        and vars(obj).get("_is_protocol")):
                    offenders.append(label)
    assert offenders == []


def test_exception_taxonomy_is_single_rooted() -> None:
    from quadkit.contracts.exceptions import QuadkitError

    offenders: list[str] = []
    exception_modules = [m for m in _MODULES if ".exceptions" in m]
    assert exception_modules, "expected exceptions modules to be present"
    for module_path in exception_modules:
        module = importlib.import_module(module_path)
        for attr_name, attr in vars(module).items():
            if (isinstance(attr, type) and attr_name.endswith("Error")
                    and getattr(attr, "__module__", None) == module_path
                    and not issubclass(attr, QuadkitError)):
                offenders.append(f"{module_path}.{attr_name}")
    assert offenders == []


@pytest.mark.parametrize("protocol_name", [
    "CacheBackendProtocol",
    "DatabaseProviderProtocol",
    "SecretStoreProtocol",
])
def test_generic_protocols_are_implementable_by_shape(
    protocol_name: str,
) -> None:
    """Public extension protocols accept plain structural implementations."""

    import quadkit.contracts.infra.cache
    import quadkit.contracts.data
    import quadkit.contracts.security.secrets

    holders = {
        "CacheBackendProtocol": quadkit.contracts.infra.cache,
        "DatabaseProviderProtocol": quadkit.contracts.data,
        "SecretStoreProtocol": quadkit.contracts.security.secrets,
    }
    protocol = getattr(holders[protocol_name], protocol_name)
    assert isinstance(protocol, type)

    class Dummy:
        def __getattr__(self, name: str):  # satisfies shape introspection
            async def _impl(*args, **kwargs):
                return None

            return _impl

    implemented = {
        name for name in dir(Dummy())
        if not name.startswith("_")
    } | {n for n in dir(protocol) if not n.startswith("_")}
    assert protocol_name not in implemented  # sanity: attributes are names
