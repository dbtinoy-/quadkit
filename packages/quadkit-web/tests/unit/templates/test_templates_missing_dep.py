import builtins
import importlib

import pytest


def test_jinja2_missing_raises(monkeypatch):
    # Simulate ImportError when trying to import jinja2
    real_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "jinja2" or name.startswith("jinja2."):
            raise ImportError("No module named 'jinja2'")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    # Unload modules to clear cache
    import sys
    sys.modules.pop("quadkit.web.templates.core", None)
    sys.modules.pop("quadkit.web.templates", None)

    # Import the module under test, then instantiate the template engine which imports jinja2 lazily
    mod = importlib.import_module("quadkit.web.templates")

    with pytest.raises(ImportError) as exc:
        mod.Jinja2Templates()

    assert "Jinja2 is required to use templates" in str(
        exc.value,
    ) or "No module named 'jinja2'" in str(exc.value)
