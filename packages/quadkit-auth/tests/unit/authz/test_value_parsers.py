"""Tests for authorization value parsers and registry."""

from __future__ import annotations

from quadkit.auth.authz._parsers import (
    ListValueParser,
    NoneValueParser,
    StringValueParser,
    ValueParserRegistry,
)


class TestStringValueParser:
    def test_plain_string(self) -> None:
        p = StringValueParser()
        assert p.can_parse("admin") is True
        assert p.parse("admin") == ["admin"]

    def test_json_list_string(self) -> None:
        p = StringValueParser()
        assert p.parse('["a", "b"]') == ["a", "b"]

    def test_json_scalar_string(self) -> None:
        p = StringValueParser()
        assert p.parse('"quoted"') == ["quoted"]

    def test_json_number_string(self) -> None:
        p = StringValueParser()
        assert p.parse("42") == ["42"]

    def test_invalid_json_falls_back_to_raw(self) -> None:
        p = StringValueParser()
        assert p.parse("{not json") == ["{not json"]

    def test_non_string_not_parseable(self) -> None:
        p = StringValueParser()
        assert p.can_parse(42) is False
        assert p.can_parse(None) is False


class TestListValueParser:
    def test_list_passthrough(self) -> None:
        p = ListValueParser()
        assert p.can_parse(["a", "b"]) is True
        assert p.parse(["a", "b"]) == ["a", "b"]

    def test_string_not_parseable(self) -> None:
        p = ListValueParser()
        assert p.can_parse("a") is False

    def test_tuple_set_and_frozenset_are_sequences(self) -> None:
        """A tuple of roles is a tuple of roles (AUTHZ-1).

        The parser required ``list`` exactly, so a principal declaring
        ``roles = ("demo_role",)`` matched no parser and the registry's
        ``str()`` fallback turned the tuple into one role named
        ``"('demo_role',)"`` — every role check then failed, with a 403 that
        told the user they lacked the role they had.
        """
        p = ListValueParser()
        assert p.parse(("a", "b")) == ["a", "b"]
        assert p.parse(frozenset({"a"})) == ["a"]
        assert sorted(p.parse({"a", "b"})) == ["a", "b"]

    def test_registry_parses_a_tuple_of_roles(self) -> None:
        reg = ValueParserRegistry()
        assert reg.parse(("demo_role",)) == ["demo_role"]
        assert reg.parse({"demo_role"}) == ["demo_role"]


class TestNoneValueParser:
    def test_none(self) -> None:
        p = NoneValueParser()
        assert p.can_parse(None) is True
        assert p.parse(None) == []

    def test_empty_list_not_none(self) -> None:
        p = NoneValueParser()
        assert p.can_parse([]) is False


class TestRegistry:
    def test_default_parsers_cover_str_list_none(self) -> None:
        reg = ValueParserRegistry()
        assert reg.parse("x") == ["x"]
        assert reg.parse(["y"]) == ["y"]
        assert reg.parse(None) == []

    def test_json_list_through_registry(self) -> None:
        reg = ValueParserRegistry()
        assert reg.parse('["r1", "r2"]') == ["r1", "r2"]

    def test_unhandled_type_stringified(self) -> None:
        reg = ValueParserRegistry()
        assert reg.parse(123) == ["123"]
        assert reg.parse(3.14) == ["3.14"]

    def test_custom_parser_prepended(self) -> None:
        class IntParser:
            def can_parse(self, val: object) -> bool:
                return isinstance(val, int)

            def parse(self, val: object) -> list[str]:
                return [f"int:{val}"]

        reg = ValueParserRegistry()
        reg.register_parser(IntParser())
        assert reg.parse(7) == ["int:7"]
        # defaults still work
        assert reg.parse("s") == ["s"]

    def test_custom_parser_ordering_first_match_wins(self) -> None:
        class EverythingParser:
            def can_parse(self, val: object) -> bool:
                return True

            def parse(self, val: object) -> list[str]:
                return ["everything"]

        reg = ValueParserRegistry()
        reg.register_parser(EverythingParser())
        assert reg.parse("s") == ["everything"]
        assert reg.parse(["l"]) == ["everything"]
        assert reg.parse(None) == ["everything"]

    def test_registry_is_thread_safe_for_register(self) -> None:
        import threading

        reg = ValueParserRegistry()
        errors: list[BaseException] = []

        def worker(i: int) -> None:
            try:
                for _ in range(50):
                    class _P:
                        def can_parse(self, val: object) -> bool:
                            return False

                        def parse(self, val: object) -> list[str]:
                            return []

                    reg.register_parser(_P())
            except BaseException as e:  # noqa: BLE001
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == []
        assert len(reg._parsers) == 3 + 8 * 50

    def test_module_level_registry(self) -> None:
        from quadkit.auth.authz import _parsers

        assert isinstance(_parsers._value_parser_registry, ValueParserRegistry)
        assert _parsers._value_parser_registry.parse("z") == ["z"]

    def test_all_exports(self) -> None:
        from quadkit.auth.authz import _parsers

        assert set(_parsers.__all__) == {
            "ListValueParser",
            "NoneValueParser",
            "StringValueParser",
            "ValueParser",
            "ValueParserRegistry",
        }
