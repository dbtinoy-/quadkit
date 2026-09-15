"""Tests for Callback contracts."""
from __future__ import annotations


def test_callback_handler_protocol_exists():
    """CallbackHandlerProtocol should exist in contracts."""
    from quadkit.contracts.ai.callbacks import CallbackHandlerProtocol
    
    assert CallbackHandlerProtocol is not None


def test_callback_handler_has_all_12_methods():
    """CallbackHandlerProtocol should have all 12 callback methods."""
    from quadkit.contracts.ai.callbacks import CallbackHandlerProtocol
    
    expected_methods = [
        "on_llm_start",
        "on_llm_new_token", 
        "on_llm_end",
        "on_llm_error",
        "on_chain_start",
        "on_chain_end",
        "on_tool_start",
        "on_tool_end",
        "on_agent_action",
        "on_agent_finish",
        "on_retriever_start",
        "on_retriever_end",
    ]
    
    for method in expected_methods:
        assert hasattr(CallbackHandlerProtocol, method), f"Missing method: {method}"


def test_callback_manager_protocol_exists():
    """CallbackManagerProtocol should exist in contracts."""
    from quadkit.contracts.ai.callbacks import CallbackManagerProtocol
    
    assert CallbackManagerProtocol is not None


def test_callback_manager_has_required_methods():
    """CallbackManagerProtocol should have register, unregister, child methods."""
    from quadkit.contracts.ai.callbacks import CallbackManagerProtocol
    
    assert hasattr(CallbackManagerProtocol, "register")
    assert hasattr(CallbackManagerProtocol, "unregister")
    assert hasattr(CallbackManagerProtocol, "child")
