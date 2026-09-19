"""Tests for serialization/__init__ module."""
import pytest


class TestSerializationLazyImports:
    """Tests for serialization module lazy imports."""

    def test_lazy_import_serialization_error(self) -> None:
        """Test lazy import of SerializationError."""
        from quadkit.serialization import SerializationError
        assert SerializationError is not None

    def test_lazy_import_json_backend(self) -> None:
        """Test lazy import of JSON_BACKEND."""
        from quadkit.serialization import JSON_BACKEND
        assert JSON_BACKEND in ("orjson", "stdlib")

    def test_lazy_import_json_decode_error(self) -> None:
        """Test lazy import of JSONDecodeError."""
        from quadkit.serialization import JSONDecodeError
        assert JSONDecodeError is not None

    def test_lazy_import_dumps(self) -> None:
        """Test lazy import of dumps."""
        from quadkit.serialization import dumps
        assert callable(dumps)

    def test_lazy_import_dumps_str(self) -> None:
        """Test lazy import of dumps_str."""
        from quadkit.serialization import dumps_str
        assert callable(dumps_str)

    def test_lazy_import_loads(self) -> None:
        """Test lazy import of loads."""
        from quadkit.serialization import loads
        assert callable(loads)

    def test_lazy_import_loads_str(self) -> None:
        """Test lazy import of loads_str."""
        from quadkit.serialization import loads_str
        assert callable(loads_str)

    def test_lazy_import_serialization_config(self) -> None:
        """Test lazy import of SerializationConfig."""
        from quadkit.serialization import SerializationConfig
        assert SerializationConfig is not None

    def test_lazy_import_json_backend_type(self) -> None:
        """Test lazy import of JSONBackend."""
        from quadkit.serialization import JSONBackend
        assert JSONBackend is not None

    def test_lazy_import_json_serializable(self) -> None:
        """Test lazy import of JSONSerializable."""
        from quadkit.serialization import JSONSerializable
        assert JSONSerializable is not None

    def test_lazy_import_json_serializer_protocol(self) -> None:
        """Test lazy import of JsonSerializerProtocol."""
        from quadkit.serialization import JsonSerializerProtocol
        assert JsonSerializerProtocol is not None

    def test_lazy_import_serializer_protocol(self) -> None:
        """Test lazy import of SerializerProtocol."""
        from quadkit.serialization import SerializerProtocol
        assert SerializerProtocol is not None

    def test_lazy_import_orjson_serializer(self) -> None:
        """Test lazy import of OrjsonSerializer."""
        from quadkit.serialization import OrjsonSerializer
        assert OrjsonSerializer is not None

    def test_lazy_import_stdlib_serializer(self) -> None:
        """Test lazy import of StdlibSerializer."""
        from quadkit.serialization import StdlibSerializer
        assert StdlibSerializer is not None

    def test_lazy_import_serializer_registry(self) -> None:
        """Test lazy import of SerializerRegistry."""
        from quadkit.serialization import SerializerRegistry
        assert SerializerRegistry is not None

    def test_lazy_import_serialization_provider(self) -> None:
        """Test lazy import of SerializationProvider."""
        from quadkit.serialization import SerializationProvider
        assert SerializationProvider is not None


class TestSerializationDir:
    """Tests for serialization.__dir__()."""

    def test_dir_includes_lazy_imports(self) -> None:
        """Test __dir__ returns all lazy import keys."""
        from quadkit import serialization
        d = dir(serialization)
        assert "dumps" in d
        assert "loads" in d
        assert "SerializationError" in d

    def test_all_in_dir_are_in_all(self) -> None:
        """Test __all__ matches __dir__."""
        from quadkit import serialization
        assert set(dir(serialization)) == set(serialization.__all__)


class TestSerializationAttributeError:
    """Tests for serialization module error handling."""

    def test_raises_attribute_error_for_unknown(self) -> None:
        """Test that unknown attributes raise AttributeError."""
        from quadkit import serialization
        with pytest.raises(AttributeError, match="has no attribute"):
            serialization.nonexistent_attribute