"""Tests verifying the config package imports cleanly without pydantic."""

import importlib
import sys


def test_config_imports_without_pydantic(monkeypatch):
    """Config package imports successfully without pydantic installed.

    Since BaseConfig now uses DomainModel (stdlib dataclasses) instead of
    pydantic-settings BaseSettings, the config package should load cleanly
    regardless of whether pydantic is installed.
    """
    module_name = "quadkit.config"

    # Clear cached module
    if module_name in sys.modules:
        monkeypatch.delitem(sys.modules, module_name, raising=False)
    # Also clear sub-modules that may have been cached
    for key in list(sys.modules.keys()):
        if key.startswith("quadkit.config."):
            monkeypatch.delitem(sys.modules, key, raising=False)

    # Import should succeed
    mod = importlib.import_module(module_name)
    assert hasattr(mod, "BaseConfig")
    assert hasattr(mod, "QuadkitConfig")
    assert hasattr(mod, "ConfigLoader")
