"""Tests for ValueObject base class."""


from dataclasses import dataclass

from quadkit.domain.models.value_object import ValueObject


@dataclass(frozen=True)
class Money(ValueObject):
    """Money value object for testing."""
    amount: int
    currency: str


@dataclass(frozen=True)
class Address(ValueObject):
    """Address value object for testing."""
    street: str
    city: str
    zip_code: str


class TestValueObject:
    """Tests for ValueObject."""

    def test_equal_values(self) -> None:
        """Test that two value objects with same values are equal."""
        m1 = Money(amount=100, currency="USD")
        m2 = Money(amount=100, currency="USD")

        assert m1 == m2

    def test_different_values_not_equal(self) -> None:
        """Test that value objects with different values are not equal."""
        m1 = Money(amount=100, currency="USD")
        m2 = Money(amount=200, currency="USD")

        assert m1 != m2

    def test_different_currency_not_equal(self) -> None:
        """Test that value objects with different currencies are not equal."""
        m1 = Money(amount=100, currency="USD")
        m2 = Money(amount=100, currency="EUR")

        assert m1 != m2

    def test_hash_equal_values(self) -> None:
        """Test that equal value objects have the same hash."""
        m1 = Money(amount=100, currency="USD")
        m2 = Money(amount=100, currency="USD")

        assert hash(m1) == hash(m2)

    def test_can_be_used_in_set(self) -> None:
        """Test that value objects can be used in sets."""
        m1 = Money(amount=100, currency="USD")
        m2 = Money(amount=100, currency="USD")
        m3 = Money(amount=200, currency="USD")

        vo_set = {m1, m2, m3}

        assert len(vo_set) == 2  # m1 and m2 are duplicates

    def test_can_be_used_as_dict_key(self) -> None:
        """Test that value objects can be used as dict keys."""
        m1 = Money(amount=100, currency="USD")
        m2 = Money(amount=100, currency="USD")

        d = {m1: "primary"}
        assert d[m2] == "primary"

    def test_inequality_with_different_type(self) -> None:
        """Test that value objects are not equal to different types."""
        m = Money(amount=100, currency="USD")

        assert (m == "not a value object") is False

    def test_equality_not_implemented_for_incompatible(self) -> None:
        """Test equality returns False for incompatible types."""
        m = Money(amount=100, currency="USD")
        result = m.__eq__(123)
        assert result is NotImplemented

    def test_not_equal_to_none(self) -> None:
        """Test value object is not equal to None."""
        m = Money(amount=100, currency="USD")
        assert (m == None) is False
        assert (m != None) is True

    def test_with_changes_basic(self) -> None:
        """Test basic with_changes functionality."""
        m = Money(amount=100, currency="USD")
        m2 = m.with_changes(amount=200)
        assert m2.amount == 200
        assert m2.currency == "USD"

    def test_with_changes_returns_new_instance(self) -> None:
        """Test that with_changes returns a new instance."""
        m = Money(amount=100, currency="USD")
        m2 = m.with_changes(amount=200)
        assert m is not m2

    def test_with_changes_original_unchanged(self) -> None:
        """Test that original is not modified."""
        m = Money(amount=100, currency="USD")
        m.with_changes(amount=200)
        assert m.amount == 100

    def test_with_changes_multiple_fields(self) -> None:
        """Test with_changes with multiple fields."""
        m = Money(amount=100, currency="USD")
        m2 = m.with_changes(amount=200, currency="EUR")
        assert m2.amount == 200
        assert m2.currency == "EUR"

    def test_with_changes_no_args(self) -> None:
        """Test with_changes with no arguments returns copy."""
        m = Money(amount=100, currency="USD")
        m2 = m.with_changes()
        assert m == m2
        assert m is not m2


class TestValueObjectInheritance:
    """Tests for ValueObject inheritance."""

    def test_subclass_can_have_defaults(self) -> None:
        """Test subclass can define default values."""

        @dataclass(frozen=True)
        class Point(ValueObject):
            x: int = 0
            y: int = 0

        p = Point()
        assert p.x == 0
        assert p.y == 0

    def test_subclass_equality(self) -> None:
        """Test equality works with subclass."""
        p1 = Address(street="123 Main", city="NYC", zip_code="10001")
        p2 = Address(street="123 Main", city="NYC", zip_code="10001")
        assert p1 == p2

    def test_subclass_with_changes(self) -> None:
        """Test with_changes works with subclass."""
        addr = Address(street="123 Main", city="NYC", zip_code="10001")
        addr2 = addr.with_changes(city="LA")
        assert addr2.city == "LA"
        assert addr2.street == "123 Main"
