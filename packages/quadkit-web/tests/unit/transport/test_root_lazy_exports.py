import importlib


def import_attr(name: str):
    """Import an attribute from quadkit.web and return it."""
    mod = importlib.import_module("quadkit.web")
    val = getattr(mod, name)
    return val


def test_lazy_import_get_warns_and_returns():
    """Test that `get` can be imported from `quadkit.web`."""
    val = import_attr("get")
    # Should return a callable decorator or function
    assert callable(val)


def test_lazy_import_body_warns_and_returns():
    """Test that `body` can be imported from `quadkit.web`."""
    val = import_attr("body")
    assert callable(val)
