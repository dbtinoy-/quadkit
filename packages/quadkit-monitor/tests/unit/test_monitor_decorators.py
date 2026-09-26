"""Tests for monitor decorators."""

import pytest
from quadkit.monitor.decorators import monitor

def test_monitor_sync_success():
    """Test sync function monitoring."""
    @monitor("sync_op", log_args=True)
    def my_func(a, b):
        return a + b
    
    assert my_func(1, 2) == 3

def test_monitor_sync_error():
    """Test sync function monitoring error."""
    @monitor("sync_op_err")
    def my_func():
        raise ValueError("test error")
    
    with pytest.raises(ValueError, match="test error"):
        my_func()

@pytest.mark.asyncio
async def test_monitor_async_success():
    """Test async function monitoring."""
    @monitor("async_op", log_args=True)
    async def my_func(a, b):
        return a + b
    
    assert await my_func(1, 2) == 3

@pytest.mark.asyncio
async def test_monitor_async_error():
    """Test async function monitoring error."""
    @monitor("async_op_err")
    async def my_func():
        raise ValueError("test async error")
    
    with pytest.raises(ValueError, match="test async error"):
        await my_func()

def test_monitor_default_name():
    """Test default naming."""
    @monitor()
    def my_default_func():
        return 1
    
    assert my_default_func() == 1
