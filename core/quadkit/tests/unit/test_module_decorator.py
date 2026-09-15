import pytest
from quadkit.di.module import Module, ModuleMetadata, module
from quadkit.di.provider import Provider

class MockProvider(Provider):
    name = "mock"

def test_module_decorator_no_args():
    """Test @module usage without parentheses."""
    @module
    class MyModule:
        pass

    assert hasattr(MyModule, "__quadkit_module__")
    meta = MyModule.__quadkit_module__
    assert isinstance(meta, ModuleMetadata)
    assert meta.name == "MyModule"
    assert meta.providers == []
    assert meta.imports == []
    assert meta.exports == []
    assert meta.__quadkit_owner__ is MyModule

def test_module_decorator_with_args():
    """Test @module(...) usage with configuration."""
    @module(
        name="CustomName",
        providers=[MockProvider],
        exports=[str]
    )
    class MyModule:
        pass

    assert MyModule.__quadkit_module__.name == "CustomName"
    assert MyModule.__quadkit_module__.providers == [MockProvider]
    assert MyModule.__quadkit_module__.exports == [str]
    assert MyModule.__quadkit_module__.__quadkit_owner__ is MyModule

def test_module_decorator_with_imports():
    """Test @module imports validation."""
    @module
    class DependencyModule:
        pass

    @module(imports=[DependencyModule])
    class MainModule:
        pass

    assert MainModule.__quadkit_module__.imports == [DependencyModule]

def test_module_decorator_preserves_class():
    """Test that the decorator returns the original class, not metadata."""
    @module
    class MyModule:
        def some_method(self):
            return 42

    instance = MyModule()
    assert instance.some_method() == 42
    assert isinstance(instance, MyModule)

def test_module_invalid_import_raises_type_error():
    """Test that importing a non-module class raises TypeError."""
    class NotAModule:
        pass

    with pytest.raises(TypeError) as exc:
        @module(imports=[NotAModule])
        class InvalidModule:
            pass
    
    assert "not decorated with @module" in str(exc.value)
