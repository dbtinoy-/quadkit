"""Tests for MCP connectors."""

from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch


class TestFilesystemConnector:
    """Tests for FilesystemConnector."""

    def test_requires_root_dir(self) -> None:
        from quadkit.ai.mcp.connectors.filesystem import FilesystemConnector

        with pytest.raises(ValueError, match="requires a non-empty root_dir"):
            FilesystemConnector(root_dir="")

    @pytest.mark.asyncio
    async def test_list_tools_includes_read_file(self) -> None:
        from quadkit.ai.mcp.connectors.filesystem import FilesystemConnector

        with patch.object(Path, "exists", return_value=True):
            connector = FilesystemConnector(root_dir="/tmp")
            tools = await connector.list_tools()

            tool_names = [t["name"] for t in tools]
            assert "read_file" in tool_names
            assert "list_directory" in tool_names

    @pytest.mark.asyncio
    async def test_list_tools_excludes_write_when_readonly(self) -> None:
        from quadkit.ai.mcp.connectors.filesystem import FilesystemConnector

        with patch.object(Path, "exists", return_value=True):
            connector = FilesystemConnector(root_dir="/tmp", read_only=True)
            tools = await connector.list_tools()

            tool_names = [t["name"] for t in tools]
            assert "write_file" not in tool_names


class TestFilesystemConnectorPaths:
    """Tests for path resolution."""

    def test_is_within_sandbox_true(self) -> None:
        from quadkit.ai.mcp.connectors.filesystem import FilesystemConnector

        with patch.object(Path, "exists", return_value=True):
            connector = FilesystemConnector(root_dir="/tmp")
            path = Path("/tmp/subdir/file.txt")
            with patch("quadkit.ai.mcp.connectors.filesystem.Path.resolve", return_value=path):
                with patch.object(Path, "relative_to", return_value=Path("subdir/file.txt")):
                    result = connector._is_within_sandbox(path)
                    assert result is True

    def test_is_within_sandbox_false(self) -> None:
        from quadkit.ai.mcp.connectors.filesystem import FilesystemConnector

        with patch.object(Path, "exists", return_value=True):
            connector = FilesystemConnector(root_dir="/tmp")
            path = Path("/etc/passwd")
            with patch.object(Path, "relative_to", side_effect=ValueError("outside")):
                result = connector._is_within_sandbox(path)
                assert result is False


class TestConnectorExports:
    """Tests for connectors module exports."""

    def test_filesystem_exported(self) -> None:
        from quadkit.ai.mcp.connectors import filesystem

        assert filesystem is not None

    def test_github_exported(self) -> None:
        from quadkit.ai.mcp.connectors import github

        assert github is not None

    def test_sql_exported(self) -> None:
        from quadkit.ai.mcp.connectors import sql

        assert sql is not None

    def test_web_fetch_exported(self) -> None:
        from quadkit.ai.mcp.connectors import web_fetch

        assert web_fetch is not None

    def test_web_search_exported(self) -> None:
        from quadkit.ai.mcp.connectors import web_search

        assert web_search is not None

    def test_slack_exported(self) -> None:
        from quadkit.ai.mcp.connectors import slack

        assert slack is not None

    def test_google_drive_exported(self) -> None:
        from quadkit.ai.mcp.connectors import google_drive

        assert google_drive is not None