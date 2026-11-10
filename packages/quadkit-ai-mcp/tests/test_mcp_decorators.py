"""Tests for MCP decorators."""

from __future__ import annotations

import pytest


class TestToolDecorator:
    """Tests for @tool decorator."""

    def test_decorator_basic(self) -> None:
        from quadkit.ai.mcp.controllers.decorators import tool

        @tool("test_tool")
        async def test_func() -> dict:
            return {}

        assert test_func._tool_config["name"] == "test_tool"
        assert test_func._tool_config["description"] == ""

    def test_decorator_with_description(self) -> None:
        from quadkit.ai.mcp.controllers.decorators import tool

        @tool("test_tool", description="A test tool")
        async def test_func() -> dict:
            return {}

        assert test_func._tool_config["name"] == "test_tool"
        assert test_func._tool_config["description"] == "A test tool"

    def test_decorator_with_method(self) -> None:
        from quadkit.ai.mcp.controllers.decorators import tool

        class MyClass:
            @tool("get_data")
            async def get_data(self) -> dict:
                return {}

        obj = MyClass()
        assert obj.get_data._tool_config["name"] == "get_data"


class TestResourceDecorator:
    """Tests for @resource decorator."""

    def test_decorator_basic(self) -> None:
        from quadkit.ai.mcp.controllers.decorators import resource

        @resource("file://config")
        async def get_config() -> str:
            return "{}"

        assert get_config._resource_config["uri_pattern"] == "file://config"
        assert get_config._resource_config["description"] == ""

    def test_decorator_with_description(self) -> None:
        from quadkit.ai.mcp.controllers.decorators import resource

        @resource("file://config", description="App configuration")
        async def get_config() -> str:
            return "{}"

        assert get_config._resource_config["uri_pattern"] == "file://config"
        assert get_config._resource_config["description"] == "App configuration"

    def test_decorator_with_name(self) -> None:
        from quadkit.ai.mcp.controllers.decorators import resource

        @resource("file://{file_id}", name="File Resource")
        async def get_file() -> str:
            return "content"

        assert get_file._resource_config["name"] == "File Resource"


class TestPromptDecorator:
    """Tests for @prompt decorator."""

    def test_decorator_basic(self) -> None:
        from quadkit.ai.mcp.controllers.decorators import prompt

        @prompt("summarize")
        async def summarize() -> str:
            return "Summarize: ..."

        assert summarize._prompt_config["name"] == "summarize"
        assert summarize._prompt_config["description"] == ""

    def test_decorator_with_description(self) -> None:
        from quadkit.ai.mcp.controllers.decorators import prompt

        @prompt("summarize", description="Generate summary")
        async def summarize() -> str:
            return "Summarize: ..."

        assert summarize._prompt_config["name"] == "summarize"
        assert summarize._prompt_config["description"] == "Generate summary"


class TestDecoratorExports:
    """Tests for decorators module exports."""

    def test_all_exported(self) -> None:
        from quadkit.ai.mcp import decorators

        assert hasattr(decorators, "tool")
        assert hasattr(decorators, "resource")
        assert hasattr(decorators, "prompt")