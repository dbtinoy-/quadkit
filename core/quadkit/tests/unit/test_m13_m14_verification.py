import pytest
from dataclasses import dataclass
from typing import Any
from quadkit.serialization.backends.json import OrjsonSerializer, StdlibSerializer
from quadkit.serialization.registry import SerializerRegistry
from quadkit.mapping.core.mapper import ObjectMapperImpl
from quadkit.validation.engine import ValidatorImpl
from quadkit.validation.rules import required, min_length
from quadkit.mapping.exceptions import MappingExecutionError

@dataclass
class UserDto:
    name: str

class TestSerializationM13:
    def test_orjson_serializer(self):
        try:
            import orjson
            serializer = OrjsonSerializer()
            data = {"name": "Test"}
            encoded = serializer.dumps(data)
            assert isinstance(encoded, bytes)
            assert b"Test" in encoded
            assert serializer.loads(encoded) == data
            
            # Test SerializerProtocol methods
            assert serializer.serialize(data) == encoded
            assert serializer.deserialize(encoded, dict) == data
        except ImportError:
            pytest.skip("orjson not available")

    def test_stdlib_serializer(self):
        serializer = StdlibSerializer()
        data = {"name": "Test"}
        encoded = serializer.dumps(data)
        assert isinstance(encoded, bytes)
        assert b"Test" in encoded
        assert serializer.loads(encoded) == data
        
        # Test SerializerProtocol methods
        assert serializer.serialize(data) == encoded
        assert serializer.deserialize(encoded, dict) == data

    def test_registry(self):
        registry = SerializerRegistry()
        serializer = StdlibSerializer()
        registry.register("application/json", serializer)
        assert registry.get("application/json") is serializer
        assert registry.negotiate("application/json").unwrap() is serializer
        assert registry.negotiate("*/*").unwrap() is serializer
        assert registry.negotiate("text/html,application/json;q=0.9").unwrap() is serializer

class TestMapperValidationM14:
    def test_auto_map_with_validation_success(self):
        mapper = ObjectMapperImpl()
        source = {"name": "Alice"}
        
        validator = ValidatorImpl().rule("name", required(), min_length(3))
        
        result = mapper.auto_map(source, UserDto, validate=True, validator=validator)
        assert isinstance(result, UserDto)
        assert result.name == "Alice"

    def test_auto_map_with_validation_failure(self):
        mapper = ObjectMapperImpl()
        source = {"name": "Al"} # Too short, min_length(3) will fail
        
        validator = ValidatorImpl().rule("name", required(), min_length(3))
        
        with pytest.raises(MappingExecutionError) as exc:
            mapper.auto_map(source, UserDto, validate=True, validator=validator)
        assert "Post-mapping validation failed" in str(exc.value)

    def test_map_with_validation_success(self):
        mapper = ObjectMapperImpl()
        mapper.register(dict, UserDto, lambda d: UserDto(name=d["name"]))
        source = {"name": "Bob"}
        
        validator = ValidatorImpl().rule("name", required(), min_length(3))
        
        result = mapper.map(source, UserDto, validate=True, validator=validator)
        assert result.name == "Bob"

    def test_map_with_validation_failure(self):
        mapper = ObjectMapperImpl()
        mapper.register(dict, UserDto, lambda d: UserDto(name=d["name"]))
        source = {"name": "Bo"}
        
        validator = ValidatorImpl().rule("name", required(), min_length(3))
        
        with pytest.raises(MappingExecutionError):
            mapper.map(source, UserDto, validate=True, validator=validator)
