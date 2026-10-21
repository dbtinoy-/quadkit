"""The package's public surface, and that it stays type-checkable.

``quadkit.storage`` imports its drivers lazily so that installing the
package does not drag in boto3, google-cloud-storage and azure-blob.
That is worth keeping — but it only works for *consumers* if the names
are also statically visible, because a type checker cannot run
``__getattr__``.

So ``__all__`` is written out by hand, and this test is the thing that
stops it drifting from the lazy map it describes. Without it the next
driver added would be importable at runtime, invisible to mypy, and
nobody would find out until an application somewhere went red.
"""

from __future__ import annotations

import importlib

import quadkit.storage as storage


def test_all_matches_the_lazy_import_map() -> None:
    assert set(storage.__all__) == set(storage._LAZY_IMPORTS) | {"__version__"}


def test_all_is_a_literal_list_so_mypy_can_read_it() -> None:
    """A computed ``__all__`` is not a public API as far as mypy is concerned."""
    source = importlib.util.find_spec("quadkit.storage")
    assert source is not None and source.origin is not None
    text = open(source.origin, encoding="utf-8").read()
    marker = text.split("__all__ = ", 1)[1]
    assert marker.startswith("[\n    \""), "__all__ must be a literal list of names"


def test_every_exported_name_actually_resolves() -> None:
    """Optional cloud drivers resolve too; they fail on *use*, not import."""
    for name in storage.__all__:
        assert getattr(storage, name) is not None


def test_dir_lists_the_same_names() -> None:
    assert set(dir(storage)) == set(storage.__all__)
