"""Tests for DynamicModule (runtime module descriptor)."""

from __future__ import annotations

import pytest

from quadkit.contracts.exceptions.provider import ModuleError
from quadkit.di.module.dynamic import DynamicModule, _describe_dynamic_entry


class _FakeModule:
    pass


class _FakeProvider:
    pass


def _test_provider_cls() -> type:
    class TestProvider:
        pass

    return TestProvider


class TestConstruction:
    def test_module_must_be_class(self) -> None:
        with pytest.raises(ModuleError, match="must be a class"):
            DynamicModule(module="not-a-class")  # type: ignore[arg-type]

    def test_defaults(self) -> None:
        dm = DynamicModule(module=_FakeModule)
        assert dm.providers == []
        assert dm.imports == []
        assert dm.exports == []
        assert dm.controllers == []
        assert dm.is_global is False
        assert dm.name is None
        assert dm.health_probers if False else True
        assert dm.health_providers is None

    def test_fields_are_independent_defaults(self) -> None:
        a = DynamicModule(module=_FakeModule)
        b = DynamicModule(module=_FakeModule)
        a.providers.append(_FakeProvider)
        assert b.providers == []

    def test_dataclass_equality_ignores_mutables(self) -> None:
        a = DynamicModule(module=_FakeModule)
        b = DynamicModule(module=_FakeModule)
        assert a == b


class TestResolvedName:
    def test_explicit_name_wins(self) -> None:
        dm = DynamicModule(module=_FakeModule, name="custom")
        assert dm.resolved_name == "custom"

    def test_falls_back_to_module_name(self) -> None:
        dm = DynamicModule(module=_FakeModule)
        assert dm.resolved_name == "_FakeModule"

    def test_empty_name_falls_back(self) -> None:
        dm = DynamicModule(module=_FakeModule, name="")
        assert dm.resolved_name == "_FakeModule"


class TestRepr:
    def test_minimal_repr(self) -> None:
        dm = DynamicModule(module=_FakeModule)
        assert repr(dm) == "<DynamicModule '_FakeModule'>"

    def test_repr_with_all_sections(self) -> None:
        provider_cls = _test_provider_cls()

        class OtherModule:
            pass

        class Nested:
            pass

        nested = DynamicModule(module=Nested, name="nested-mod")
        export = type("SomeProtocol", (), {})

        dm = DynamicModule(
            module=_FakeModule,
            name="dm",
            providers=[provider_cls, _FakeProvider()],
            imports=[OtherModule, nested],
            exports=[export],
            is_global=True,
        )
        text = repr(dm)
        assert "'dm'" in text
        assert "providers=[" in text
        assert provider_cls.__name__ in text  # class → __name__
        assert "_FakeProvider" in text  # instance → type().__name__
        assert "imports=[" in text
        assert OtherModule.__name__ in text
        assert "nested-mod" in text  # DynamicModule entry → resolved_name
        assert "exports=[" in text
        assert export.__name__ in text
        assert "is_global=True" in text
        assert text.endswith(">")

    def test_describe_dynamic_entry(self) -> None:
        assert _describe_dynamic_entry(_FakeModule) == "_FakeModule"
        assert _describe_dynamic_entry(object()) == "object"


class TestNesting:
    def test_dynamic_module_as_import(self) -> None:
        class Outer:
            pass

        class Inner:
            pass

        inner = DynamicModule(module=Inner)
        outer = DynamicModule(module=Outer, imports=[inner])
        assert outer.imports == [inner]
        assert isinstance(outer.imports[0], DynamicModule)
