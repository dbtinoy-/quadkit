"""Bulk module registration consumes collections, never mutates their types."""

from collections.abc import Callable, Iterable

import pytest

from quadkit.app.base import Application, AppState
from quadkit.di.module import DynamicModule, Module, module


@module()
class FirstModule(Module):
    pass


@module()
class SecondModule(Module):
    pass


@pytest.mark.parametrize("collection", [list, tuple, iter])
def test_typed_dynamic_module_iterables_preserve_order_and_identity(
    collection: Callable[[list[DynamicModule]], Iterable[DynamicModule]],
) -> None:
    app = Application()
    originals = [DynamicModule(module=FirstModule), DynamicModule(module=SecondModule)]
    app.add_modules(collection(originals))
    assert len(app._modules) == 2
    assert app._modules[0] is originals[0]
    assert app._modules[1] is originals[1]
    assert [item.module for item in originals] == [FirstModule, SecondModule]


@pytest.mark.parametrize("collection", [list, tuple, iter])
def test_iterable_registration_retains_pre_start_guard(
    collection: Callable[[list[DynamicModule]], Iterable[DynamicModule]],
) -> None:
    app = Application()
    app._state = AppState.RUNNING
    with pytest.raises(RuntimeError, match="Cannot add_module after boot"):
        app.add_modules(collection([DynamicModule(module=FirstModule)]))
    assert app._modules == []
