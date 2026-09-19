"""Unit tests for mapping module components."""

from dataclasses import dataclass

from quadkit.mapping import MappingModule
from quadkit.mapping.config import MappingConfig
from quadkit.mapping.core.mapper import ObjectMapperImpl
from quadkit.mapping.exceptions import MappingError
from quadkit.mapping.types import MapperProtocol


class TestMappingModule:
    """Test MappingModule functionality."""

    def test_module_creation(self):
        """MappingModule is a valid Module subclass."""
        from quadkit.di.module import Module

        assert issubclass(MappingModule, Module)
        assert MappingModule is not None

    def test_module_with_config(self):
        """MappingConfig can be constructed with custom values."""
        config = MappingConfig(strict=True)
        assert config.strict is True

    def test_module_is_a_module_subclass(self):
        """MappingModule is a static Module subclass — no configure factory."""
        from quadkit.di.module import Module

        assert issubclass(MappingModule, Module)

    def test_module_class_is_accessible(self):
        """MappingModule is importable and accessible from quadkit.mapping."""
        assert MappingModule is not None


class TestMappingConfig:
    """Test mapping configuration."""

    def test_config_defaults(self):
        """Test default mapping configuration."""
        config = MappingConfig()
        assert config.strict is False
        assert config.auto_map is True

    def test_config_with_values(self):
        """Test configuration with custom values."""
        config = MappingConfig(
            strict=True,
            ignore_unknown=True,
            case_sensitive=True,
        )
        assert config.strict is True
        assert config.ignore_unknown is True
        assert config.case_sensitive is True


class TestObjectMapper:
    """Test ObjectMapperImpl functionality."""

    def test_mapper_creation(self):
        """Test object mapper can be created."""
        mapper = ObjectMapperImpl()
        assert mapper is not None

    def test_mapper_has_map_method(self):
        """Test mapper has map method."""
        mapper = ObjectMapperImpl()
        assert hasattr(mapper, "map")

    def test_mapper_has_map_to_method(self):
        """Test mapper has auto_map method."""
        mapper = ObjectMapperImpl()
        assert hasattr(mapper, "auto_map")

    @dataclass
    class SourceClass:
        name: str
        age: int

    @dataclass
    class TargetClass:
        name: str
        age: int
        city: str | None = None

    def test_map_simple_object(self):
        """Test auto-mapping simple object by matching field names."""
        mapper = ObjectMapperImpl()
        source = self.SourceClass(name="John", age=30)

        result = mapper.auto_map(source, self.TargetClass)
        assert result.name == "John"
        assert result.age == 30

    def test_map_with_field_mapping(self):
        """Test mapping with an explicitly registered mapper function."""
        mapper = ObjectMapperImpl()
        source = self.SourceClass(name="John", age=30)

        mapper.register(
            self.SourceClass,
            self.TargetClass,
            lambda s: self.TargetClass(name=s.name, age=s.age),
        )
        result = mapper.map(source, self.TargetClass)
        assert result.name == "John"
        assert result.age == 30


class TestMapperProtocol:
    """Test MapperProtocol."""

    def test_protocol_exists(self):
        """Verify protocol is importable."""
        assert MapperProtocol is not None

    def test_protocol_has_map_method(self):
        """Verify protocol defines map method."""
        # Protocol should define map signature
        assert hasattr(MapperProtocol, "map")


class TestMappingExceptions:
    """Test mapping exceptions."""

    def test_mapping_error_creation(self):
        """Test creating mapping error."""
        error = MappingError("Mapping failed")
        assert error.message == "Mapping failed"

    def test_mapping_error_with_cause(self):
        """Test mapping error with cause."""
        cause = ValueError("Invalid value")
        error = MappingError("Mapping failed", cause=cause)
        assert error.cause == cause


class MapSource:
    def __init__(self, id: int, name: str, active: bool = True) -> None:
        self.id = id
        self.name = name
        self.active = active


class MapTarget:
    def __init__(self, id: int, name: str, is_active: bool = True, extra: str | None = None) -> None:
        self.id = id
        self.name = name
        self.is_active = is_active
        self.extra = extra


class TestMapperFieldMapping:
    """Test mapper field mapping scenarios."""

    def test_rename_field(self):
        """Test renaming fields via a registered mapper function."""
        mapper = ObjectMapperImpl()
        source = MapSource(id=1, name="Test", active=True)

        mapper.register(
            MapSource,
            MapTarget,
            lambda s: MapTarget(id=s.id, name=s.name, is_active=s.active),
        )
        result = mapper.map(source, MapTarget)
        assert result.is_active is True

    def test_ignore_extra_fields(self):
        """Test auto-mapping ignores extra fields in source dict."""
        mapper = ObjectMapperImpl()
        source = {"id": 1, "name": "Test", "extra_field": "ignored"}

        result = mapper.auto_map(source, MapTarget)
        assert result.name == "Test"

    def test_nested_mapping(self):
        """Test nested object auto-mapping by field name."""
        mapper = ObjectMapperImpl()

        @dataclass
        class InnerSource:
            value: int

        @dataclass
        class InnerTarget:
            value: int

        source = InnerSource(value=42)
        result = mapper.auto_map(source, InnerTarget)
        assert result.value == 42


class TestMapperCollections:
    """Test mapper with collections."""

    def test_map_list(self):
        """Test mapping a list of objects using auto_map_many."""
        mapper = ObjectMapperImpl()
        source = [
            {"id": 1, "name": "A"},
            {"id": 2, "name": "B"},
        ]

        @dataclass
        class Item:
            id: int
            name: str

        results = mapper.auto_map_many(source, Item)
        assert len(results) == 2
        assert results[0].name == "A"

    def test_map_dict(self):
        """Test try_map returns Ok result on successful mapping."""
        mapper = ObjectMapperImpl()

        @dataclass
        class ItemSource:
            id: int

        @dataclass
        class Item:
            id: int

        source = ItemSource(id=42)
        mapper.register(ItemSource, Item, lambda s: Item(id=s.id))
        result = mapper.try_map(source, Item)
        assert result.is_ok()
        assert result.unwrap().id == 42
