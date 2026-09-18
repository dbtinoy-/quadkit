"""Tests for Tools + LCEL contracts (G-03 parity)."""
from __future__ import annotations


def test_tool_decorator_basic():
    """@tool decorator should create a callable tool."""
    from quadkit.contracts.ai.tools import tool
    
    @tool("add")
    def add(a: int, b: int) -> int:
        """Add two numbers."""
        return a + b
    
    assert add.name == "add"
    assert add.invoke(1, 2) == 3


def test_tool_with_description():
    """@tool should preserve docstring as description."""
    from quadkit.contracts.ai.tools import tool
    
    @tool("multiply")
    def multiply(a: int, b: int) -> int:
        """Multiply two numbers together."""
        return a * b
    
    assert multiply.description == "Multiply two numbers together."


def test_tool_invoke_with_kwargs():
    """Tool should support kwargs in invoke."""
    from quadkit.contracts.ai.tools import tool
    
    @tool("greet")
    def greet(name: str, greeting: str = "Hello") -> str:
        """Greet someone."""
        return f"{greeting}, {name}!"
    
    result = greet.invoke(name="Alice")
    assert "Alice" in result


def test_structured_tool():
    """StructuredTool should support tools with structured output."""
    from quadkit.contracts.ai.tools import StructuredTool
    
    def add(a: int, b: int) -> int:
        return a + b
    
    st = StructuredTool(
        name="add",
        description="Add two numbers",
        func=add,
    )
    assert st.name == "add"
    assert st.invoke(a=1, b=2) == 3
