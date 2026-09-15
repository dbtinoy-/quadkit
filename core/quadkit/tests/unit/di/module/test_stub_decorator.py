"""Tests for the require_stub parameter on the @module() decorator."""

from __future__ import annotations

import pytest

from quadkit.di.module.base import Module
from quadkit.di.module.constants import MODULE_METADATA_ATTR
from quadkit.di.module.decorator import module
from quadkit.di.module.metadata import ModuleMetadata


class TestRequireStub:
    def test_default_require_stub_is_false(self) -> None:
        @module()
        class MyModule(Module):
            pass

        meta: ModuleMetadata = getattr(MyModule, MODULE_METADATA_ATTR)
        assert meta.require_stub is False

    def test_require_stub_true(self) -> None:
        @module(require_stub=True)
        class MyModule(Module):
            pass

        meta: ModuleMetadata = getattr(MyModule, MODULE_METADATA_ATTR)
        assert meta.require_stub is True

    def test_require_stub_preserved_in_metadata(self) -> None:
        @module(require_stub=True, is_global=False)
        class MyModule(Module):
            pass

        meta: ModuleMetadata = getattr(MyModule, MODULE_METADATA_ATTR)
        assert meta.require_stub is True
        assert meta.is_global is False

    def test_require_stub_false_explicit(self) -> None:
        @module(require_stub=False)
        class MyModule(Module):
            pass

        meta: ModuleMetadata = getattr(MyModule, MODULE_METADATA_ATTR)
        assert meta.require_stub is False

    def test_require_stub_bare_decorator_defaults_false(self) -> None:
        @module
        class MyModule(Module):
            pass

        meta: ModuleMetadata = getattr(MyModule, MODULE_METADATA_ATTR)
        assert meta.require_stub is False

    def test_metadata_dataclass_default(self) -> None:
        meta = ModuleMetadata(name="TestModule")
        assert meta.require_stub is False

    def test_metadata_dataclass_explicit_true(self) -> None:
        meta = ModuleMetadata(name="TestModule", require_stub=True)
        assert meta.require_stub is True
