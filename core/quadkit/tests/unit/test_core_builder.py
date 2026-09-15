"""Tests for core/builder module."""

import pytest

from quadkit.primitives.builder import AbstractBuilder, builder_field, buildable


class TestAbstractBuilder:
    """Tests for AbstractBuilder base class."""

    def test_copy_returns_deepcopy(self) -> None:
        """Test that copy returns a deep copy."""

        class ConcreteBuilder(AbstractBuilder[str]):
            def __init__(self) -> None:
                super().__init__()
                self._value = "test"

            def build(self) -> str:
                return self._value

        builder = ConcreteBuilder()
        copied = builder.copy()
        assert copied.build() == "test"
        assert copied is not builder
        assert copied._value == builder._value

    def test_copy_is_independent(self) -> None:
        """Test that copied builder is independent."""

        class ConcreteBuilder(AbstractBuilder[str]):
            def __init__(self) -> None:
                super().__init__()
                self.items = []

            def build(self) -> str:
                return ",".join(self.items)

        builder = ConcreteBuilder()
        builder.items.append("a")
        copied = builder.copy()
        copied.items.append("b")
        assert "b" not in builder.items
        assert "b" in copied.items


class TestBuilderFieldDecorator:
    """Tests for builder_field decorator."""

    def test_decorator_marks_function(self) -> None:
        """Test builder_field marks function with attribute."""

        @builder_field
        def my_field() -> None:
            pass

        assert hasattr(my_field, "__is_builder_field__")
        assert my_field.__is_builder_field__ is True

    def test_decorator_with_callable(self) -> None:
        """Test builder_field works as decorator on callable."""

        def plain_function(x: int) -> int:
            return x * 2

        result = builder_field(plain_function)
        assert result is plain_function
        assert hasattr(result, "__is_builder_field__")

    def test_decorator_with_string(self) -> None:
        """Test builder_field returns string when passed string."""
        result = builder_field("field_name")
        assert result == "field_name"


class TestBuildableDecorator:
    """Tests for @buildable decorator."""

    def test_buildable_creates_builder_method(self) -> None:
        """Test that @buildable adds builder() method to class."""

        @buildable
        class Simple:
            def __init__(self, value: str) -> None:
                self.value = value

        assert hasattr(Simple, "builder")
        assert callable(Simple.builder)

    def test_buildable_builder_returns_builder_instance(self) -> None:
        """Test that builder() returns a builder instance."""

        @buildable
        class Simple:
            def __init__(self, value: str) -> None:
                self.value = value

        builder = Simple.builder()
        assert isinstance(builder, AbstractBuilder)

    def test_buildable_with_required_params(self) -> None:
        """Test building with required parameters."""

        @buildable
        class User:
            def __init__(self, name: str, email: str) -> None:
                self.name = name
                self.email = email

        user = User.builder().with_name("John").with_email("john@example.com").build()
        assert user.name == "John"
        assert user.email == "john@example.com"

    def test_buildable_with_optional_params(self) -> None:
        """Test building with optional parameters."""

        @buildable
        class User:
            def __init__(self, name: str, age: int = 0) -> None:
                self.name = name
                self.age = age

        user = User.builder().with_name("John").build()
        assert user.name == "John"
        assert user.age == 0

    def test_buildable_missing_required_raises(self) -> None:
        """Test that missing required params raises TypeError."""

        @buildable
        class User:
            def __init__(self, name: str, email: str) -> None:
                self.name = name
                self.email = email

        builder = User.builder().with_name("John")
        with pytest.raises(TypeError, match="missing required arguments"):
            builder.build()

    def test_buildable_with_wrong_param_raises(self) -> None:
        """Test that wrong parameter raises appropriate error."""

        @buildable
        class User:
            def __init__(self, name: str) -> None:
                self.name = name

        builder = User.builder()
        with pytest.raises(AttributeError):
            builder.with_nonexistent("value")

    def test_buildable_fluent_interface(self) -> None:
        """Test fluent interface returns same builder."""

        @buildable
        class User:
            def __init__(self, name: str, email: str, age: int = 0) -> None:
                self.name = name
                self.email = email
                self.age = age

        builder = User.builder()
        result = builder.with_name("John").with_email("john@example.com").with_age(30)
        assert result is builder

    def test_buildable_preserves_class_attributes(self) -> None:
        """Test that @buildable preserves original class attributes."""

        @buildable
        class User:
            CLASS_ATTR = "class_value"

            def __init__(self, name: str) -> None:
                self.name = name

        assert User.CLASS_ATTR == "class_value"
        assert "builder" in dir(User)

    def test_buildable_with_multiple_required(self) -> None:
        """Test buildable with multiple required parameters."""

        @buildable
        class Config:
            def __init__(self, host: str, port: int, ssl: bool = False) -> None:
                self.host = host
                self.port = port
                self.ssl = ssl

        config = Config.builder().with_host("localhost").with_port(8080).build()
        assert config.host == "localhost"
        assert config.port == 8080
        assert config.ssl is False

    def test_buildable_with_all_params_set(self) -> None:
        """Test building with all parameters including optional."""

        @buildable
        class Config:
            def __init__(self, host: str, port: int = 80, ssl: bool = True) -> None:
                self.host = host
                self.port = port
                self.ssl = ssl

        config = Config.builder().with_host("example.com").with_port(443).with_ssl(False).build()
        assert config.host == "example.com"
        assert config.port == 443
        assert config.ssl is False


class TestBuildableWithTypeHints:
    """Tests for @buildable with type annotations."""

    def test_buildable_with_type_hints(self) -> None:
        """Test that type hints work correctly."""

        @buildable
        class Person:
            def __init__(self, name: str, age: int) -> None:
                self.name = name
                self.age = age

        builder = Person.builder()
        assert hasattr(builder, "with_name")
        assert hasattr(builder, "with_age")

    def test_buildable_type_conversion(self) -> None:
        """Test that values are passed through correctly."""

        @buildable
        class Numbers:
            def __init__(self, integer: int, floating: float, string: str) -> None:
                self.integer = integer
                self.floating = floating
                self.string = string

        nums = Numbers.builder().with_integer(42).with_floating(3.14).with_string("test").build()
        assert nums.integer == 42
        assert nums.floating == 3.14
        assert nums.string == "test"


class TestBuildableEdgeCases:
    """Edge case tests for @buildable."""

    def test_buildable_empty_init(self) -> None:
        """Test buildable with no parameters."""

        @buildable
        class Empty:
            def __init__(self) -> None:
                pass

        obj = Empty.builder().build()
        assert isinstance(obj, Empty)

    def test_buildable_with_only_defaults(self) -> None:
        """Test buildable with only optional parameters."""

        @buildable
        class Optional:
            def __init__(self, a: int = 1, b: str = "default") -> None:
                self.a = a
                self.b = b

        obj = Optional.builder().build()
        assert obj.a == 1
        assert obj.b == "default"
