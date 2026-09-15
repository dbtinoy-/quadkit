"""Tests for core/lazy module."""

from quadkit.primitives.lazy import LazyImport


class TestLazyImport:
    """Tests for LazyImport class."""

    def test_init_not_loaded(self) -> None:
        """Test that LazyImport is not loaded on creation."""
        imp = LazyImport("json")
        assert imp.is_initialized() is False

    def test_load_on_access(self) -> None:
        """Test that module is loaded on first access."""
        imp = LazyImport("json")
        _ = imp.dumps
        assert imp.is_initialized() is True

    def test_attribute_access(self) -> None:
        """Test attribute access to module."""
        imp = LazyImport("json")
        dumps_func = imp.dumps
        assert callable(dumps_func)

    def test_repr_not_loaded(self) -> None:
        """Test repr when not loaded."""
        imp = LazyImport("os")
        assert "not loaded" in repr(imp)

    def test_repr_loaded(self) -> None:
        """Test repr when loaded."""
        imp = LazyImport("os")
        _ = imp.name
        assert "loaded" in repr(imp)
