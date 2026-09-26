"""Tests for cache abstractions"""

from inspect import signature
from typing import Any, Optional, Protocol

import pytest

from quadkit.contracts.infra.cache import CacheBackendProtocol


class TestCacheBackendAbstraction:
    """Test the CacheBackendProtocol abstract base class"""

    def test_cache_backend_is_protocol(self):
        """Test that CacheBackendProtocol is a Protocol"""
        assert issubclass(CacheBackendProtocol, Protocol)

    def test_cache_backend_cannot_be_instantiated(self):
        """Test that CacheBackendProtocol cannot be instantiated directly"""
        with pytest.raises(TypeError):
            CacheBackendProtocol()

    def test_cache_backend_has_all_abstract_methods(self):
        """Test that CacheBackendProtocol defines all expected abstract methods"""
        expected_methods = [
            "get",
            "set",
            "delete",
            "exists",
            "clear",
            "get_many",
            "set_many",
            "delete_many",
            "health_check",
        ]

        for method_name in expected_methods:
            assert hasattr(CacheBackendProtocol, method_name), f"Missing method: {method_name}"
            method = getattr(CacheBackendProtocol, method_name)
            assert callable(method), f"Method {method_name} is not callable"

    def test_cache_backend_method_signatures(self):
        """Test that CacheBackendProtocol methods have correct signatures"""
        # Test get method signature
        get_sig = signature(CacheBackendProtocol.get)
        assert "key" in get_sig.parameters
        assert get_sig.parameters["key"].annotation == "str"

        # Test set method signature
        set_sig = signature(CacheBackendProtocol.set)
        assert "key" in set_sig.parameters
        assert "value" in set_sig.parameters
        assert "ttl" in set_sig.parameters
        assert set_sig.parameters["key"].annotation == "str"
        assert set_sig.parameters["ttl"].annotation == "int | None"

        # Test delete method signature
        delete_sig = signature(CacheBackendProtocol.delete)
        assert "key" in delete_sig.parameters
        assert delete_sig.parameters["key"].annotation == "str"

        # Test exists method signature
        exists_sig = signature(CacheBackendProtocol.exists)
        assert "key" in exists_sig.parameters
        assert exists_sig.parameters["key"].annotation == "str"

        # Test get_many method signature
        get_many_sig = signature(CacheBackendProtocol.get_many)
        assert "keys" in get_many_sig.parameters
        assert get_many_sig.parameters["keys"].annotation == "list[str]"

        # Test set_many method signature
        set_many_sig = signature(CacheBackendProtocol.set_many)
        assert "items" in set_many_sig.parameters
        assert "ttl" in set_many_sig.parameters
        assert set_many_sig.parameters["items"].annotation == "dict[str, Any]"

        # Test delete_many method signature
        delete_many_sig = signature(CacheBackendProtocol.delete_many)
        assert "keys" in delete_many_sig.parameters
        assert delete_many_sig.parameters["keys"].annotation == "list[str]"

    def test_cache_backend_method_docstrings(self):
        """Test that CacheBackendProtocol methods have proper docstrings"""
        methods_with_docs = [
            "get",
            "set",
            "delete",
            "exists",
            "clear",
            "get_many",
            "set_many",
            "delete_many",
            "health_check",
        ]

        for method_name in methods_with_docs:
            method = getattr(CacheBackendProtocol, method_name)
            assert method.__doc__ is not None, f"Method {method_name} missing docstring"
            assert (
                len(method.__doc__.strip()) > 0
            ), f"Method {method_name} has empty docstring"

    def test_cache_backend_health_check_return_type(self):
        """Test that health_check method has correct return type annotation"""
        health_check_sig = signature(CacheBackendProtocol.health_check)
        assert health_check_sig.return_annotation == "HealthCheckResult"
