"""Tests for instrumentation decorators."""

import pytest
from unittest.mock import MagicMock

from quadkit.monitor.instrumentation.decorators import (
    traced,
    metered,
    traced_class,
    TracedClass,
)
from quadkit.monitor.services.core import ObservabilityService

@pytest.fixture
def obs_service():
    service = MagicMock(spec=ObservabilityService)
    # mock trace context manager
    span = MagicMock()
    service.trace.return_value.__enter__.return_value = span
    # mock histogram
    service.histogram.return_value.record = MagicMock()
    return service

def test_traced_sync_success(obs_service):
    """Test sync traced decorator."""
    @traced("sync_span", service=obs_service)
    def my_func(a):
        return a + 1
    
    assert my_func(1) == 2
    obs_service.trace.assert_called_once_with("sync_span")

def test_traced_sync_error(obs_service):
    """Test sync traced error."""
    @traced("sync_span_err", service=obs_service)
    def my_func():
        raise ValueError("test error")
    
    with pytest.raises(ValueError, match="test error"):
        my_func()
    
    span = obs_service.trace.return_value.__enter__.return_value
    span.set_attribute.assert_called_with("error", True)
    span.add_event.assert_called()

@pytest.mark.asyncio
async def test_traced_async_success(obs_service):
    """Test async traced decorator."""
    @traced("async_span", service=obs_service)
    async def my_func(a):
        return a + 1
    
    assert await my_func(1) == 2
    obs_service.trace.assert_called_once_with("async_span")

@pytest.mark.asyncio
async def test_traced_async_error(obs_service):
    """Test async traced error."""
    @traced("async_span_err", service=obs_service)
    async def my_func():
        raise ValueError("test async error")
    
    with pytest.raises(ValueError, match="test async error"):
        await my_func()
    
    span = obs_service.trace.return_value.__enter__.return_value
    span.set_attribute.assert_called_with("error", True)
    span.add_event.assert_called()

def test_metered_sync_success(obs_service):
    """Test sync metered decorator."""
    @metered("sync_metric", service=obs_service)
    def my_func(a):
        return a + 1
    
    assert my_func(1) == 2
    obs_service.histogram.assert_called_once_with("sync_metric")
    obs_service.histogram.return_value.record.assert_called_once()

@pytest.mark.asyncio
async def test_metered_async_success(obs_service):
    """Test async metered decorator."""
    @metered("async_metric", service=obs_service)
    async def my_func(a):
        return a + 1
    
    assert await my_func(1) == 2
    obs_service.histogram.assert_called_once_with("async_metric")
    obs_service.histogram.return_value.record.assert_called_once()

def test_traced_class():
    """Test traced_class decorator."""
    @traced_class("MyClass")
    class MyClass:
        def my_method(self):
            return 1
            
        def _private_method(self):
            return 2
            
        @classmethod
        def my_classmethod(cls):
            pass
            
    obj = MyClass()
    assert obj.my_method() == 1
    assert obj._private_method() == 2

def test_traced_class_trace_private():
    """Test traced_class decorator with trace_private."""
    @traced_class("MyClass2", trace_private=True)
    class MyClass2:
        def _private_method(self):
            return 2
            
    obj = MyClass2()
    assert obj._private_method() == 2
