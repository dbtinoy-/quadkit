"""GitHub connector — browse repositories, read files, create issues, search code.

Tools exposed:
- ``github_list_repos``   — List repositories for a user or organisation
- ``github_get_file``     — Read a file's content from a repository
- ``github_create_issue`` — Open a new issue in a repository
- ``github_search_code``  — Search code across GitHub
- ``github_list_issues``  — List open issues in a repository

Resources exposed:
- ``github://{owner}/{repo}``          — Repository metadata
- ``github://{owner}/{repo}/{path}``   — File content

All requests use the GitHub REST API v3 over HTTPS with *aiohttp*.
Token-based auth is applied on every request; API errors (including
rate limits) surface as tool error results with the GitHub message.
"""

from __future__ import annotations

from typing import Any

from quadkit.ai.mcp.types import MCPToolDefinition, MCPToolResult
from quadkit.logging import (
    get_logger,
)
from quadkit.serialization import dumps_str

logger = get_logger(__name__)

_GITHUB_API = "https://api.github.com"


class GitHubConnector:
    """GitHub access via MCP tools and resources.

    Exposes common GitHub operations as MCP tools. Requires a personal access
    token (classic or fine-grained) set in the constructor.

    Example::

        connector = GitHubConnector(token="ghp_xxxx")
    """

    def __init__(
        self,
        token: str,
        *,
        api_url: str = _GITHUB_API,
    ) -> None:
        """Initialize the GitHub connector.

        Args:
            token: GitHub personal access token.
            api_url: Override base URL for GitHub Enterprise.

        Raises:
            ValueError: If ``token`` is empty.
        """
        if not token:
            raise ValueError("GitHubConnector requires a non-empty token")
        self._token = token
        self._api_url = api_url.rstrip("/")

    # ------------------------------------------------------------------
    # MCPToolProviderProtocol interface
    # ------------------------------------------------------------------

    async def list_tools(self) -> list[dict[str, Any]]:
        """Return tool definitions."""
        return [
            MCPToolDefinition(
                name="github_list_repos",
                description="List repositories for a GitHub user or organisation",
                input_schema={
                    "type": "object",
                    "properties": {
                        "owner": {
                            "type": "string",
                            "description": "GitHub username or organisation name",
                        },
                        "type": {
                            "type": "string",
                            "description": "Filter: 'all', 'public', 'private', 'forks', 'sources'",
                            "default": "public",
                        },
                        "per_page": {
                            "type": "integer",
                            "description": "Results per page (max 100)",
                            "default": 30,
                        },
                    },
                    "required": ["owner"],
                },
            ).to_dict(),
            MCPToolDefinition(
                name="github_get_file",
                description="Read a file's content from a GitHub repository",
                input_schema={
                    "type": "object",
                    "properties": {
                        "owner": {"type": "string"},
                        "repo": {"type": "string"},
                        "path": {
                            "type": "string",
                            "description": "File path (e.g. 'src/main.py')",
                        },
                        "ref": {
                            "type": "string",
                            "description": "Branch, tag, or commit SHA (default: default branch)",
                            "default": "",
                        },
                    },
                    "required": ["owner", "repo", "path"],
                },
            ).to_dict(),
            MCPToolDefinition(
                name="github_create_issue",
                description="Create a new issue in a GitHub repository",
                input_schema={
                    "type": "object",
                    "properties": {
                        "owner": {"type": "string"},
                        "repo": {"type": "string"},
                        "title": {"type": "string"},
                        "body": {
                            "type": "string",
                            "description": "Issue body (Markdown)",
                            "default": "",
                        },
                        "labels": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Label names",
                            "default": [],
                        },
                    },
                    "required": ["owner", "repo", "title"],
                },
            ).to_dict(),
            MCPToolDefinition(
                name="github_search_code",
                description="Search code across GitHub repositories",
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "GitHub code search query (supports qualifiers like repo:, language:)",
                        },
                        "per_page": {
                            "type": "integer",
                            "description": "Results per page (max 30)",
                            "default": 10,
                        },
                    },
                    "required": ["query"],
                },
            ).to_dict(),
            MCPToolDefinition(
                name="github_list_issues",
                description="List open issues in a GitHub repository",
                input_schema={
                    "type": "object",
                    "properties": {
                        "owner": {"type": "string"},
                        "repo": {"type": "string"},
                        "state": {
                            "type": "string",
                            "description": "Issue state: 'open', 'closed', 'all'",
                            "default": "open",
                        },
                        "per_page": {
                            "type": "integer",
                            "default": 30,
                        },
                    },
                    "required": ["owner", "repo"],
                },
            ).to_dict(),
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> MCPToolResult:
        """Dispatch tool calls.

        Args:
            name: Tool name.
            arguments: Tool arguments dict.

        Returns:
            MCPToolResult with JSON data or error.
        """
        from quadkit.contracts.mcp.exceptions import MCPToolCallError

        dispatch = {
            "github_list_repos": self._list_repos,
            "github_get_file": self._get_file,
            "github_create_issue": self._create_issue,
            "github_search_code": self._search_code,
            "github_list_issues": self._list_issues,
        }
        handler = dispatch.get(name)
        if handler is None:
            raise MCPToolCallError(
                message=f"Unknown GitHub tool: {name}", tool_name=name
            )
        return await handler(arguments)

    # ------------------------------------------------------------------
    # MCPResourceProviderProtocol interface
    # ------------------------------------------------------------------

    async def list_resources(self) -> list[dict[str, Any]]:
        """Return empty list — resources are accessed by URI directly."""
        return []

    async def read_resource(self, uri: str) -> dict[str, Any]:
        """Read a GitHub resource by URI.

        Args:
            uri: ``github://owner/repo`` or ``github://owner/repo/path``

        Returns:
            MCP resource content dict.
        """
        path = uri.removeprefix("github://")
        parts = path.split("/", 2)
        if len(parts) == 2:
            owner, repo = parts
            result = await self._get_repo_info(owner, repo)
        elif len(parts) >= 3:
            owner, repo, file_path = parts[0], parts[1], parts[2]
            result = await self._get_file(
                {"owner": owner, "repo": repo, "path": file_path}
            )
        else:
            return {
                "contents": [
                    {"uri": uri, "mimeType": "text/plain", "text": "Invalid URI"}
                ]
            }
        text = result.content[0]["text"] if result.content else ""
        return {
            "contents": [{"uri": uri, "mimeType": "application/json", "text": text}]
        }

    # ------------------------------------------------------------------
    # Tool implementations
    # ------------------------------------------------------------------

    async def _list_repos(self, arguments: dict[str, Any]) -> MCPToolResult:
        owner = arguments.get("owner", "")
        repo_type = arguments.get("type", "public")
        per_page = min(int(arguments.get("per_page") or 30), 100)
        url = f"{self._api_url}/users/{owner}/repos"
        params = {"type": repo_type, "per_page": per_page}
        data = await self._get(url, params)
        if isinstance(data, dict) and "message" in data:
            return MCPToolResult.error("GitHub API request failed")
        repos = [
            {
                "name": r["name"],
                "description": r.get("description"),
                "url": r["html_url"],
            }
            for r in (data if isinstance(data, list) else [])
        ]
        return MCPToolResult.text(dumps_str(repos))

    async def _get_file(self, arguments: dict[str, Any]) -> MCPToolResult:
        owner = arguments.get("owner", "")
        repo = arguments.get("repo", "")
        path = arguments.get("path", "")
        ref = arguments.get("ref", "") or ""
        url = f"{self._api_url}/repos/{owner}/{repo}/contents/{path}"
        params = {"ref": ref} if ref else {}
        data = await self._get(url, params)
        if isinstance(data, dict):
            if "message" in data:
                return MCPToolResult.error("GitHub API request failed")
            encoding = data.get("encoding", "")
            content_raw = data.get("content", "")
            if encoding == "base64":
                import base64

                try:
                    content = base64.b64decode(content_raw).decode(
                        "utf-8", errors="replace"
                    )
                except (ValueError, UnicodeDecodeError, TypeError):
                    content = content_raw
            else:
                content = content_raw
            return MCPToolResult.text(content)
        return MCPToolResult.error("Unexpected response from GitHub API")

    async def _create_issue(self, arguments: dict[str, Any]) -> MCPToolResult:
        owner = arguments.get("owner", "")
        repo = arguments.get("repo", "")
        title = arguments.get("title", "")
        body = arguments.get("body", "") or ""
        labels: list[str] = list(arguments.get("labels") or [])
        url = f"{self._api_url}/repos/{owner}/{repo}/issues"
        payload: dict[str, Any] = {"title": title, "body": body}
        if labels:
            payload["labels"] = labels
        data = await self._post(url, payload)
        if isinstance(data, dict):
            if "message" in data and "url" not in data:
                return MCPToolResult.error("GitHub API request failed")
            return MCPToolResult.text(
                dumps_str(
                    {"issue_number": data.get("number"), "url": data.get("html_url")}
                )
            )
        return MCPToolResult.error("Unexpected response from GitHub API")

    async def _search_code(self, arguments: dict[str, Any]) -> MCPToolResult:
        query = arguments.get("query", "")
        per_page = min(int(arguments.get("per_page") or 10), 30)
        url = f"{self._api_url}/search/code"
        data = await self._get(url, {"q": query, "per_page": per_page})
        if isinstance(data, dict):
            if "message" in data:
                return MCPToolResult.error("GitHub API request failed")
            items = [
                {
                    "name": i["name"],
                    "path": i["path"],
                    "repo": i["repository"]["full_name"],
                    "url": i["html_url"],
                }
                for i in data.get("items", [])
            ]
            return MCPToolResult.text(dumps_str(items))
        return MCPToolResult.error("Unexpected response from GitHub API")

    async def _list_issues(self, arguments: dict[str, Any]) -> MCPToolResult:
        owner = arguments.get("owner", "")
        repo = arguments.get("repo", "")
        state = arguments.get("state", "open")
        per_page = min(int(arguments.get("per_page") or 30), 100)
        url = f"{self._api_url}/repos/{owner}/{repo}/issues"
        data = await self._get(url, {"state": state, "per_page": per_page})
        if isinstance(data, dict) and "message" in data:
            return MCPToolResult.error("GitHub API request failed")
        issues = [
            {
                "number": i["number"],
                "title": i["title"],
                "state": i["state"],
                "url": i["html_url"],
            }
            for i in (data if isinstance(data, list) else [])
            if "pull_request" not in i  # exclude PRs
        ]
        return MCPToolResult.text(dumps_str(issues))

    async def _get_repo_info(self, owner: str, repo: str) -> MCPToolResult:
        url = f"{self._api_url}/repos/{owner}/{repo}"
        data = await self._get(url, {})
        if isinstance(data, dict) and "message" in data:
            return MCPToolResult.error("GitHub API request failed")
        return MCPToolResult.text(dumps_str(data))

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def _get(self, url: str, params: dict[str, Any]) -> Any:
        try:
            import aiohttp
        except ImportError:
            return {"message": "aiohttp is required for GitHubConnector"}

        try:
            async with aiohttp.ClientSession(headers=self._headers()) as session:
                async with session.get(
                    url, params=params, timeout=aiohttp.ClientTimeout(total=15)
                ) as resp:
                    return await resp.json(content_type=None)
        except Exception as exc:  # noqa: BLE001 — external GitHub API boundary
            error_type = type(exc).__name__
            logger.warning("github_get_failed", error_type=error_type)
            return {"message": f"GitHub request failed ({error_type})"}

    async def _post(self, url: str, payload: dict[str, Any]) -> Any:
        try:
            import aiohttp
        except ImportError:
            return {"message": "aiohttp is required for GitHubConnector"}

        try:
            async with aiohttp.ClientSession(headers=self._headers()) as session:
                async with session.post(
                    url, json=payload, timeout=aiohttp.ClientTimeout(total=15)
                ) as resp:
                    return await resp.json(content_type=None)
        except Exception as exc:  # noqa: BLE001 — external GitHub API boundary
            error_type = type(exc).__name__
            logger.warning("github_post_failed", error_type=error_type)
            return {"message": f"GitHub request failed ({error_type})"}


__all__ = ["GitHubConnector"]
