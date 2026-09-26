"""Scenario coverage for the in-memory specification engine.

Full operator matrix for :class:`FieldSpecification` (eq/ne/gt/gte/lt/
lte/in/contains/startswith/endswith, missing fields, unsupported
operators), composition via ``and_`` / ``or_`` / ``not_`` and the ``&`` /
``|`` / ``~`` overloads, composite and builder assembly, and the module
utility factories.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from quadkit.sql.specification.memory import (
    AndMemorySpecification,
    CompositeMemorySpecification,
    CustomSpecification,
    FieldSpecification,
    MemorySpecificationBuilder,
    NotMemorySpecification,
    OrMemorySpecification,
    and_specs,
    field_contains,
    field_equals,
    field_greater_than,
    matches,
    not_spec,
    or_specs,
)


@dataclass
class Product:
    name: str
    price: float
    stock: int
    active: bool


@pytest.fixture
def products() -> list[Product]:
    return [
        Product("widget", 9.99, 10, True),
        Product("gadget", 49.99, 0, True),
        Product("doohickey", 5.50, 100, False),
    ]


# ── FieldSpecification operator matrix ──────────────────────────────


@pytest.mark.parametrize(
    ("field", "operator", "value", "expected"),
    [
        ("name", "eq", "widget", {0}),
        ("name", "ne", "widget", {1, 2}),
        ("price", "gt", 10.0, {1}),
        ("price", "gte", 10.0, {1}),
        ("price", "lt", 10.0, {0, 2}),
        ("price", "lte", 9.99, {0, 2}),
        ("name", "in", ("widget", "doohickey"), {0, 2}),
        ("name", "contains", "gad", {1}),
        ("name", "startswith", "wi", {0}),
        ("name", "endswith", "y", {2}),
    ],
)
def test_field_specification_operators(
    products: list[Product], field: str, operator: str, value: Any, expected: set[int]
) -> None:
    spec = FieldSpecification(field, value, operator)
    got = {i for i, p in enumerate(products) if spec.is_satisfied_by(p)}
    assert got == expected


def test_field_specification_operator_case_insensitive() -> None:
    spec = FieldSpecification("name", "widget", "EQ")
    assert spec.is_satisfied_by(Product("widget", 0, 0, True))


def test_field_specification_missing_field() -> None:
    # getattr default None: eq matches None, comparisons raise TypeError
    missing = FieldSpecification("nonexistent", None, "eq")
    assert missing.is_satisfied_by(Product("x", 1, 1, True))

    with pytest.raises(TypeError):
        FieldSpecification("nonexistent", 1, "gt").is_satisfied_by(
            Product("x", 1, 1, True)
        )


def test_field_specification_contains_none_field() -> None:
    spec = FieldSpecification("nonexistent", "x", "contains")
    assert not spec.is_satisfied_by(Product("x", 1, 1, True))


def test_field_specification_unsupported_operator() -> None:
    spec = FieldSpecification("name", "x", "regex")
    with pytest.raises(ValueError, match="Unsupported operator: regex"):
        spec.is_satisfied_by(Product("x", 1, 1, True))


# ── Composition ─────────────────────────────────────────────────────


def test_and_or_not_composition(products: list[Product]) -> None:
    cheap = FieldSpecification("price", 10.0, "lt")
    active = FieldSpecification("active", True, "eq")

    both = cheap.and_(active)
    assert isinstance(both, AndMemorySpecification)
    assert [p.name for p in products if both.is_satisfied_by(p)] == ["widget"]

    either = cheap.or_(active)
    assert isinstance(either, OrMemorySpecification)
    assert {p.name for p in products if either.is_satisfied_by(p)} == {
        "widget",
        "doohickey",
        "gadget",
    }

    negated = active.not_()
    assert isinstance(negated, NotMemorySpecification)
    assert [p.name for p in products if negated.is_satisfied_by(p)] == ["doohickey"]


def test_operator_overloads_and_repr(products: list[Product]) -> None:
    cheap = FieldSpecification("price", 10.0, "lt")
    active = FieldSpecification("active", True, "eq")

    combined = cheap & active
    assert isinstance(combined, AndMemorySpecification)
    assert "AND" in repr(combined)

    either = cheap | active
    assert isinstance(either, OrMemorySpecification)
    assert "OR" in repr(either)

    negated = ~active
    assert isinstance(negated, NotMemorySpecification)
    assert repr(negated) == f"(NOT {active!r})"


def test_nested_composition() -> None:
    s1 = CustomSpecification(lambda p: p.price < 10)
    s2 = CustomSpecification(lambda p: p.stock > 0)
    s3 = CustomSpecification(lambda p: p.active)

    nested = (s1 & s2) | ~s3
    assert nested.is_satisfied_by(Product("a", 5, 5, False))  # (T & T) | T
    assert not nested.is_satisfied_by(Product("b", 50, 5, True))  # (F & T) | F
    assert nested.is_satisfied_by(Product("c", 50, 5, False))  # (F & T) | T
    assert not nested.is_satisfied_by(Product("d", 50, 5, True))  # (F & T) | F


# ── Composite specification ─────────────────────────────────────────


def test_composite_specification(products: list[Product]) -> None:
    cheap = FieldSpecification("price", 10.0, "lt")
    active = FieldSpecification("active", True, "eq")
    stocky = FieldSpecification("stock", 50, "gte")

    all_specs = CompositeMemorySpecification(cheap, active, stocky, operator="AND")
    matches_and = [p.name for p in products if all_specs.is_satisfied_by(p)]
    # none is simultaneously cheap, active AND stocky (widget stock=10)
    assert matches_and == []

    any_spec = CompositeMemorySpecification(
        cheap,
        active,
        stocky,
        operator="or",  # normalised to OR
    )
    matches_or = [p.name for p in products if any_spec.is_satisfied_by(p)]
    assert matches_or == ["widget", "gadget", "doohickey"]

    with pytest.raises(ValueError, match="Unsupported operator: XOR"):
        CompositeMemorySpecification(cheap, operator="XOR").is_satisfied_by(products[0])


# ── Builder ─────────────────────────────────────────────────────────


def test_builder_empty_builds_always_true() -> None:
    spec = MemorySpecificationBuilder[Product]().build()
    assert spec.is_satisfied_by(Product("x", 0, 0, False))


def test_builder_single_spec_passthrough() -> None:
    field_spec = FieldSpecification("name", "widget", "eq")
    spec = MemorySpecificationBuilder[Product]().field("name", "widget").build()
    assert spec is field_spec or spec.is_satisfied_by(Product("widget", 0, 0, True))
    # single spec is returned as-is
    built = MemorySpecificationBuilder[Product]().field("name", "widget").build()
    assert isinstance(built, FieldSpecification)


def test_builder_multiple_specs_and() -> None:
    spec = (
        MemorySpecificationBuilder[Product]()
        .field("price", 10.0, "lt")
        .field("active", True, "eq")
        .and_operator()
        .build()
    )
    assert isinstance(spec, CompositeMemorySpecification)
    assert spec.operator == "AND"
    assert [p.name for p in products_fixture() if spec.is_satisfied_by(p)] == ["widget"]


def test_builder_or_operator_and_custom() -> None:
    spec = (
        MemorySpecificationBuilder[Product]()
        .field("price", 40.0, "gt")
        .custom(lambda p: p.stock > 50)
        .or_operator()
        .build()
    )
    assert spec.operator == "OR"
    assert [p.name for p in products_fixture() if spec.is_satisfied_by(p)] == [
        "gadget",
        "doohickey",
    ]


def products_fixture() -> list[Product]:
    return [
        Product("widget", 9.99, 10, True),
        Product("gadget", 49.99, 0, True),
        Product("doohickey", 5.50, 100, False),
    ]


# ── Utility factories ───────────────────────────────────────────────


def test_utility_factories() -> None:
    eq_factory = field_equals("name", "widget")
    assert isinstance(eq_factory(), FieldSpecification)
    assert eq_factory().is_satisfied_by(Product("widget", 0, 0, True))

    gt_factory = field_greater_than("price", 10.0)
    spec = gt_factory()
    assert spec.operator == "gt"
    assert spec.is_satisfied_by(Product("x", 49.99, 0, True))

    contains_factory = field_contains("name", "gad")
    assert contains_factory().is_satisfied_by(Product("gadget", 0, 0, True))
    assert not contains_factory().is_satisfied_by(Product("widget", 0, 0, True))

    m = matches("stock", 10)
    assert isinstance(m, FieldSpecification)
    assert m.operator == "eq"
    assert m.is_satisfied_by(Product("x", 0, 10, True))


def test_utility_combinators() -> None:
    s1 = CustomSpecification(lambda p: p.price < 10)
    s2 = CustomSpecification(lambda p: p.stock > 50)
    s3 = CustomSpecification(lambda p: p.active)

    anded = and_specs(s1, s2, s3)
    assert anded.is_satisfied_by(Product("x", 5, 100, True))
    assert not anded.is_satisfied_by(Product("y", 50, 100, True))

    ored = or_specs(s1, s2, s3)
    assert ored.is_satisfied_by(Product("z", 5, 100, False))  # first two match
    assert not ored.is_satisfied_by(Product("w", 50, 0, False))  # none match

    negated = not_spec(s1)
    assert isinstance(negated, NotMemorySpecification)
    assert negated.is_satisfied_by(Product("x", 50, 0, True))
    assert not negated.is_satisfied_by(Product("y", 5, 0, True))
