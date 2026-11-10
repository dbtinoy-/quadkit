"""MCP built-in connectors — optional pre-built tool/resource providers.

Each connector implements the ``MCPToolProvider`` and/or ``MCPResourceProvider``
protocol and is registered automatically when the corresponding section of
``MCPConfig.connectors`` is configured.

Available connectors
--------------------
FilesystemConnector
    Read (and optionally write) local files inside a sandboxed root directory.
SQLConnector
    Execute safe, read-only parameterized SQL against any database exposed via
    ``DatabaseProviderProtocol``.
WebFetchConnector
    Fetch and return the text content of arbitrary public URLs.
WebSearchConnector
    Search the web via Brave Search, SerpAPI, or Google Custom Search.
GitHubConnector
    Browse repositories, read files, create issues, and search code on GitHub.
SlackConnector
    List channels, read history, post messages, and search in a Slack workspace.
GoogleDriveConnector
    List and read Google Docs, Sheets, and Slides from Google Drive.
"""

from __future__ import annotations

from quadkit.ai.mcp.connectors.filesystem import FilesystemConnector
from quadkit.ai.mcp.connectors.github import GitHubConnector
from quadkit.ai.mcp.connectors.google_drive import GoogleDriveConnector
from quadkit.ai.mcp.connectors.slack import SlackConnector
from quadkit.ai.mcp.connectors.sql import SQLConnector
from quadkit.ai.mcp.connectors.web_fetch import WebFetchConnector
from quadkit.ai.mcp.connectors.web_search import WebSearchConnector

__all__ = [
    "FilesystemConnector",
    "GitHubConnector",
    "GoogleDriveConnector",
    "SQLConnector",
    "SlackConnector",
    "WebFetchConnector",
    "WebSearchConnector",
]
