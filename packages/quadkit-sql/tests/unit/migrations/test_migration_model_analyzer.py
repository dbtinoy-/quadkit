"""Tests for the migration ModelAnalyzer (domain model → table definition).

NOTE: no ``from __future__ import annotations`` here — ModelAnalyzer reads
raw ``dataclass.field.type`` values, and stringified (PEP 563) annotations
would silently degrade to VARCHAR, defeating the type-mapping assertions.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional, Union

import pytest

from quadkit.domain import DomainModel
from quadkit.sql.migrations.base import MigrationError
from quadkit.sql.migrations.model_analyzer import ModelAnalyzer


@dataclass
class User(DomainModel):
    id: int
    name: str
    email: str | None = None
    age: int = 0
    active: bool = True
    tags: list[str] = field(default_factory=list)


@pytest.fixture
def analyzer() -> ModelAnalyzer:
    return ModelAnalyzer()


def _col(table: Any, name: str) -> Any:
    for c in table.columns:
        if c.name == name:
            return c
    raise AssertionError(f"column {name} not found in {table.name}")


class TestAnalyzeModel:
    def test_non_domain_model_rejected(self, analyzer: ModelAnalyzer) -> None:
        class NotAModel:
            pass

        with pytest.raises(MigrationError, match="must inherit from DomainModel"):
            analyzer.analyze_model(NotAModel)  # type: ignore[arg-type]

    def test_table_name_from_camel_case(self, analyzer: ModelAnalyzer) -> None:
        @dataclass
        class UserProfile(DomainModel):
            id: int

        table = analyzer.analyze_model(UserProfile)
        assert table.name == "user_profile"

    def test_table_name_from_meta(self, analyzer: ModelAnalyzer) -> None:
        @dataclass
        class User(DomainModel):
            id: int

            class Meta:
                table_name = "app_users"

        table = analyzer.analyze_model(User)
        assert table.name == "app_users"

    def test_explicit_table_name_param(self, analyzer: ModelAnalyzer) -> None:
        table = analyzer.analyze_model(User, table_name="custom")
        assert table.name == "custom"

    def test_field_type_mapping(self, analyzer: ModelAnalyzer) -> None:
        table = analyzer.analyze_model(User)
        assert _col(table, "id").type_sql == "INTEGER"
        assert _col(table, "name").type_sql == "VARCHAR"
        assert _col(table, "age").type_sql == "INTEGER"
        assert _col(table, "active").type_sql == "BOOLEAN"

    def test_optional_field_nullable(self, analyzer: ModelAnalyzer) -> None:
        table = analyzer.analyze_model(User)
        assert _col(table, "email").nullable is True
        assert _col(table, "email").type_sql == "VARCHAR"
        assert _col(table, "name").nullable is False

    def test_id_is_primary_key(self, analyzer: ModelAnalyzer) -> None:
        table = analyzer.analyze_model(User)
        assert _col(table, "id").primary_key is True
        assert _col(table, "name").primary_key is False

    def test_list_of_str_is_array(self, analyzer: ModelAnalyzer) -> None:
        table = analyzer.analyze_model(User)
        assert _col(table, "tags").type_sql == "VARCHAR[]"

    def test_default_values_formatted(self, analyzer: ModelAnalyzer) -> None:
        table = analyzer.analyze_model(User)
        assert _col(table, "age").default == "0"
        assert _col(table, "active").default == "TRUE"

    def test_default_string_quoted(self, analyzer: ModelAnalyzer) -> None:
        @dataclass
        class Greeting(DomainModel):
            id: int
            text: str = "hello"

        table = analyzer.analyze_model(Greeting)
        assert _col(table, "text").default == "'hello'"

    def test_none_default_is_null(self, analyzer: ModelAnalyzer) -> None:
        @dataclass
        class Nulls(DomainModel):
            id: int
            note: str | None = None

        table = analyzer.analyze_model(Nulls)
        assert _col(table, "note").default == "NULL"


class TestFieldMetadata:
    def test_unique_index_and_description(self, analyzer: ModelAnalyzer) -> None:
        @dataclass
        class Thing(DomainModel):
            id: int
            slug: str = field(metadata={"unique": True, "index": True, "description": "URL slug"})

        table = analyzer.analyze_model(Thing)
        col = _col(table, "slug")
        assert col.unique is True
        assert col.index is True
        assert col.comment == "URL slug"

    def test_foreign_key_metadata_override(self, analyzer: ModelAnalyzer) -> None:
        @dataclass
        class Post(DomainModel):
            id: int
            owner_id: int = field(metadata={"foreign_key": "users.id"})

        table = analyzer.analyze_model(Post)
        assert _col(table, "owner_id").foreign_key == "users.id"

    def test_list_of_domain_model_is_foreign_key(self, analyzer: ModelAnalyzer) -> None:
        @dataclass
        class Author(DomainModel):
            id: int

        @dataclass
        class Book(DomainModel):
            id: int
            authors: list[Author] = field(default_factory=list)

        table = analyzer.analyze_model(Book)
        col = _col(table, "authors")
        assert col.type_sql == "INTEGER"
        assert col.foreign_key == "author.id"


class TestTypeHelpers:
    def test_camel_to_snake(self, analyzer: ModelAnalyzer) -> None:
        assert analyzer._camel_to_snake("UserProfile") == "user_profile"  # noqa: SLF001
        assert analyzer._camel_to_snake("userID") == "user_id"  # noqa: SLF001
        assert analyzer._camel_to_snake("simple") == "simple"  # noqa: SLF001

    def test_sql_type_string_enum(self, analyzer: ModelAnalyzer) -> None:
        from enum import Enum

        class Color(str, Enum):
            RED = "red"

        assert analyzer._get_sql_type(Color) == "VARCHAR"  # noqa: SLF001

    def test_sql_type_int_subclass(self, analyzer: ModelAnalyzer) -> None:
        class UserId(int):
            pass

        assert analyzer._get_sql_type(UserId) == "INTEGER"  # noqa: SLF001

    def test_sql_type_forward_ref_string(self, analyzer: ModelAnalyzer) -> None:
        assert analyzer._get_sql_type("FutureModel") == "VARCHAR"  # noqa: SLF001

    def test_sql_type_unknown_defaults_varchar(self, analyzer: ModelAnalyzer) -> None:
        class Weird:
            pass

        assert analyzer._get_sql_type(Weird) == "VARCHAR"  # noqa: SLF001

    def test_is_optional_variants(self, analyzer: ModelAnalyzer) -> None:
        opt: type = Optional[str]  # noqa: UP045
        combo: type = Union[str, int]  # noqa: UP007
        assert analyzer._is_optional_type(opt) is True  # noqa: SLF001
        assert analyzer._is_optional_type(opt) is True  # noqa: SLF001
        assert analyzer._is_optional_type(str | None) is True  # noqa: SLF001
        assert analyzer._is_optional_type(str) is False  # noqa: SLF001
        assert analyzer._is_optional_type(combo) is False  # noqa: SLF001

    def test_format_default_value(self, analyzer: ModelAnalyzer) -> None:
        assert analyzer._format_default_value("x") == "'x'"  # noqa: SLF001
        assert analyzer._format_default_value(True) == "TRUE"  # noqa: SLF001
        assert analyzer._format_default_value(False) == "FALSE"  # noqa: SLF001
        assert analyzer._format_default_value(3.5) == "3.5"  # noqa: SLF001
        assert analyzer._format_default_value(None) == "NULL"  # noqa: SLF001


class TestStringifiedAnnotations:
    """PEP 563 (``from __future__ import annotations``) models must map to
    real SQL types, not silently degrade to VARCHAR."""

    def test_future_annotations_model(self, analyzer: ModelAnalyzer, tmp_path) -> None:
        import sys

        mod_src = tmp_path / "future_mod.py"
        mod_src.write_text(
            "from __future__ import annotations\n"
            "from dataclasses import dataclass\n"
            "from typing import List, Optional\n"
            "from quadkit.domain import DomainModel\n\n"
            "@dataclass\n"
            "class FutureUser(DomainModel):\n"
            "    id: int\n"
            "    name: str\n"
            "    email: Optional[str] = None\n"
            "    tags: List[str] = None  # type: ignore[assignment]\n",
            encoding="utf-8",
        )
        sys.path.insert(0, str(tmp_path))
        try:
            import importlib

            future_mod = importlib.import_module("future_mod")
        finally:
            sys.path.remove(str(tmp_path))

        table = analyzer.analyze_model(future_mod.FutureUser)
        cols = {c.name: c for c in table.columns}
        assert cols["id"].type_sql == "INTEGER"
        assert cols["name"].type_sql == "VARCHAR"
        assert cols["email"].type_sql == "VARCHAR"
        assert cols["email"].nullable is True
        assert cols["tags"].type_sql == "VARCHAR[]"

    def test_unresolvable_forward_ref_falls_back(self, analyzer: ModelAnalyzer) -> None:
        @dataclass
        class Mysterious(DomainModel):
            id: int
            payload: "DoesNotExist" = None  # type: ignore[name-defined]

        # Unresolvable string annotation → VARCHAR default (no crash).
        table = analyzer.analyze_model(Mysterious)
        assert _col(table, "payload").type_sql == "VARCHAR"


class TestTableMetadata:
    def test_meta_indexes_and_constraints(self, analyzer: ModelAnalyzer) -> None:
        @dataclass
        class Thing(DomainModel):
            id: int

            class Meta:
                indexes = ["ix_thing_id"]
                constraints = ["chk_positive"]

        table = analyzer.analyze_model(Thing)
        assert "ix_thing_id" in table.indexes
        assert "chk_positive" in table.constraints

    def test_datetime_mapping(self, analyzer: ModelAnalyzer) -> None:
        @dataclass
        class Timestamped(DomainModel):
            id: int
            created_at: datetime = field(default_factory=datetime.utcnow)

        table = analyzer.analyze_model(Timestamped)
        assert _col(table, "created_at").type_sql == "TIMESTAMP"
