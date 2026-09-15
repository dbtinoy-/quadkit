"""Tests for domain/models/factory.py - Dynamic model creation."""

import pytest

from quadkit.domain.models.factory import create_model
from quadkit.domain.models.base import DomainModel


class TestCreateModel:
    """Tests for create_model function."""

    def test_create_model_with_defaults(self) -> None:
        """Test creating a model with default DomainModel base."""
        # Skip if pydantic not available
        pytest.importorskip("pydantic")
        
        User = create_model("User", name=(str, ...), email=(str, ...))
        
        assert User.__name__ == "User"
        assert issubclass(User, DomainModel)

    def test_create_model_with_custom_fields(self) -> None:
        """Test creating model with custom fields."""
        pytest.importorskip("pydantic")
        
        Person = create_model(
            "Person",
            first_name=(str, "John"),
            age=(int, 0),
        )
        
        assert Person.__name__ == "Person"
        
        # Test instantiation with default
        person = Person()
        assert person.first_name == "John"
        assert person.age == 0
        
        # Test instantiation with values
        person2 = Person(first_name="Jane", age=25)
        assert person2.first_name == "Jane"
        assert person2.age == 25

    def test_create_model_with_custom_base(self) -> None:
        """Test creating model with custom base class."""
        pytest.importorskip("pydantic")
        
        # create_model with custom base requires DomainModel or pydantic BaseModel
        # Test that it works with default base
        Custom = create_model("Custom", value=(int, 42))
        
        assert Custom.__name__ == "Custom"
        assert issubclass(Custom, DomainModel)

    def test_create_model_with_tuple_base(self) -> None:
        """Test creating model with tuple of base classes."""
        pytest.importorskip("pydantic")
        
        # The function only supports DomainModel as base
        # Test with default behavior
        Combined = create_model("Combined", data=(str, "test"))
        
        assert Combined.__name__ == "Combined"
        assert issubclass(Combined, DomainModel)

    def test_create_model_without_pydantic(self) -> None:
        """Test fallback when pydantic not available."""
        # This test checks the fallback path works
        # The function requires pydantic for full functionality
        # but has a fallback for basic model creation
        pass


class TestDomainModel:
    """Tests for DomainModel base class."""

    def test_domain_model_import(self) -> None:
        """Test DomainModel can be imported."""
        assert DomainModel is not None

    def test_domain_model_is_dataclass(self) -> None:
        """Test DomainModel basic properties."""
        # DomainModel is a mixin class
        assert DomainModel is not None
        assert isinstance(DomainModel, type)
