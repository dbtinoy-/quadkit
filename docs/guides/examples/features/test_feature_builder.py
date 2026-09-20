"""Feature tour: `@buildable` — fluent construction for plain classes.

Decorate a class and it gains `Invoice.builder()` with a `with_<field>`
method per constructor parameter and a `build()` that assembles the
object. No dataclass ceremony, no mutable halfway objects handed around:
the builder accumulates, the class constructs.
"""

import pytest

from quadkit.primitives.builder import AbstractBuilder, buildable


@buildable
class Invoice:
    def __init__(self, number: str, total: int, currency: str = "EUR") -> None:
        self.number = number
        self.total = total
        self.currency = currency


def test_fluent_build() -> None:
    invoice = (
        Invoice.builder()
        .with_number("INV-0042")
        .with_total(9900)
        .with_currency("USD")
        .build()
    )
    assert (invoice.number, invoice.total, invoice.currency) == (
        "INV-0042",
        9900,
        "USD",
    )


def test_defaults_apply_when_field_omitted() -> None:
    invoice = Invoice.builder().with_number("INV-0007").with_total(100).build()
    assert invoice.currency == "EUR"


def test_missing_required_field_surfaces_at_build() -> None:
    builder = Invoice.builder().with_number("INV-0009")
    with pytest.raises(TypeError, match="total"):
        builder.build()


def test_unknown_field_is_rejected() -> None:
    builder = Invoice.builder()
    with pytest.raises((AttributeError, TypeError)):
        builder.with_discount(10)  # type: ignore[attr-defined]


def test_copy_produces_independent_builder() -> None:
    base = Invoice.builder().with_number("INV-0010").with_total(500)
    assert isinstance(base, AbstractBuilder)

    branched = base.copy().with_currency("GBP")
    built_base = base.build()
    built_branch = branched.build()

    assert built_base.currency == "EUR"
    assert built_branch.currency == "GBP"
    assert built_base.total == built_branch.total == 500
