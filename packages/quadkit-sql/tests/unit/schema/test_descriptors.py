"""Tests for schema index/constraint/relationship descriptors."""

from __future__ import annotations

from quadkit.sql.schema.descriptors import (
    BelongsTo,
    Constraint,
    HasMany,
    Index,
    ManyToMany,
)


class TestIndex:
    def test_string_columns_normalized(self) -> None:
        idx = Index("ix_email", "email")
        assert idx.columns == ["email"]

    def test_list_columns_preserved(self) -> None:
        idx = Index("ix_ab", ["a", "b"])
        assert idx.columns == ["a", "b"]

    def test_to_sql_basic(self) -> None:
        sql = Index("ix_email", "email").to_sql("users")
        assert sql == "CREATE INDEX ix_email ON users (email)"

    def test_to_sql_unique(self) -> None:
        sql = Index("ux_email", "email", unique=True).to_sql("users")
        assert sql == "CREATE UNIQUE INDEX ux_email ON users (email)"

    def test_to_sql_multi_column(self) -> None:
        sql = Index("ix_ab", ["a", "b"]).to_sql("t")
        assert sql == "CREATE INDEX ix_ab ON t (a, b)"

    def test_to_sql_partial_condition(self) -> None:
        sql = Index(
            "ix_active", "status", condition="active = true"
        ).to_sql("users")
        assert sql.endswith(" WHERE active = true")


class TestConstraint:
    def test_to_sql_check(self) -> None:
        sql = Constraint("ck_age", "age >= 0").to_sql()
        assert sql == "CONSTRAINT ck_age CHECK (age >= 0)"

    def test_to_sql_custom_type(self) -> None:
        sql = Constraint("uq_code", "code", type="UNIQUE").to_sql()
        assert sql == "CONSTRAINT uq_code UNIQUE (code)"


class TestRelationships:
    def test_has_many(self) -> None:
        rel = HasMany(target="Order", foreign_key="user_id")
        assert rel.target == "Order"
        assert rel.foreign_key == "user_id"
        assert rel.local_key == "id"

    def test_belongs_to(self) -> None:
        rel = BelongsTo(target="User", foreign_key="user_id")
        assert rel.target == "User"
        assert rel.owner_key == "id"

    def test_many_to_many(self) -> None:
        rel = ManyToMany(
            target="Tag",
            pivot_table="user_tags",
            foreign_key="user_id",
            related_key="tag_id",
        )
        assert rel.pivot_table == "user_tags"
        assert rel.related_key == "tag_id"
