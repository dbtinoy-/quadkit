"""Google Drive connector — list and read Docs, Sheets, Slides as MCP resources.

Resources exposed (read-only):
- ``gdrive://files``        — List files in the configured Drive folder
- ``gdrive://{file_id}``    — Export/read a file by Drive ID

Authentication uses a Google service account JSON key. If ``impersonated_email``
is provided the connector will use domain-wide delegation to act on behalf of
that user.

External dependencies (all optional — guarded at runtime):
- ``google-auth``  — ``google.oauth2.service_account``, ``google.auth.transport.requests``
- ``aiohttp``      — async HTTP client
"""

from __future__ import annotations

import asyncio
from typing import Any

from quadkit.ai.mcp.types import MCPResource, MCPToolDefinition, MCPToolResult
from quadkit.logging import (
    get_logger,
)
from quadkit.serialization import dumps_str

logger = get_logger(__name__)

_DRIVE_API = "https://www.googleapis.com/drive/v3"
_EXPORT_TYPES: dict[str, str] = {
    "application/vnd.google-apps.document": "text/plain",
    "application/vnd.google-apps.spreadsheet": "text/csv",
    "application/vnd.google-apps.presentation": "text/plain",
}
_SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
]


class GoogleDriveConnector:
    """Google Drive read access via MCP tools and resources.

    Only read operations are exposed. The service account must have View access
    to the files that will be returned. For organisation-wide access supply
    ``impersonated_email`` together with a service account that has
    domain-wide delegation enabled.

    Example::

        connector = GoogleDriveConnector(
            service_account_json='{"type": "service_account", ...}',
            impersonated_email="user@example.com",
        )
    """

    def __init__(
        self,
        service_account_json: str,
        *,
        impersonated_email: str = "",
        folder_id: str = "root",
        max_files: int = 100,
    ) -> None:
        """Initialize the Google Drive connector.

        Args:
            service_account_json: Raw JSON string of a Google service account key file.
            impersonated_email: Email of the user to impersonate (domain-wide delegation).
            folder_id: Drive folder ID to list; defaults to the root of My Drive.
            max_files: Maximum files to return when listing.

        Raises:
            ValueError: If ``service_account_json`` is empty.
        """
        if not service_account_json:
            raise ValueError("GoogleDriveConnector requires service_account_json")
        self._sa_json = service_account_json
        self._impersonated_email = impersonated_email
        self._folder_id = folder_id
        self._max_files = max_files
        self._credentials: Any = None

    # ------------------------------------------------------------------
    # MCPToolProviderProtocol interface
    # ------------------------------------------------------------------

    async def list_tools(self) -> list[dict[str, Any]]:
        """Return tool definitions."""
        return [
            MCPToolDefinition(
                name="gdrive_list_files",
                description=(
                    "List files in the configured Google Drive folder. "
                    "Returns file names, IDs, MIME types, and last-modified timestamps."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Optional Drive search query (e.g. \"name contains 'report'\")",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of files to return",
                            "default": 50,
                        },
                    },
                },
            ).to_dict(),
            MCPToolDefinition(
                name="gdrive_read_file",
                description="Export and read the text content of a Google Docs/Sheets/Slides file",
                input_schema={
                    "type": "object",
                    "properties": {
                        "file_id": {
                            "type": "string",
                            "description": "Google Drive file ID",
                        }
                    },
                    "required": ["file_id"],
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
            "gdrive_list_files": self._list_files,
            "gdrive_read_file": self._read_file,
        }
        handler = dispatch.get(name)
        if handler is None:
            raise MCPToolCallError(
                message=f"Unknown Google Drive tool: {name}", tool_name=name
            )
        return await handler(arguments)

    # ------------------------------------------------------------------
    # MCPResourceProviderProtocol interface
    # ------------------------------------------------------------------

    async def list_resources(self) -> list[dict[str, Any]]:
        """Return Drive file listing resource."""
        return [
            MCPResource(
                uri="gdrive://files",
                name="Google Drive Files",
                description=f"Files in folder {self._folder_id}",
                mime_type="application/json",
            ).to_dict()
        ]

    async def read_resource(self, uri: str) -> dict[str, Any]:
        """Read a Drive resource by URI.

        Args:
            uri: ``gdrive://files`` or ``gdrive://{file_id}``

        Returns:
            MCP resource content dict.
        """
        if uri == "gdrive://files":
            result = await self._list_files({})
        else:
            file_id = uri.removeprefix("gdrive://")
            result = await self._read_file({"file_id": file_id})
        text = result.content[0]["text"] if result.content else "{}"
        return {
            "contents": [{"uri": uri, "mimeType": "application/json", "text": text}]
        }

    # ------------------------------------------------------------------
    # Tool implementations
    # ------------------------------------------------------------------

    async def _list_files(self, arguments: dict[str, Any]) -> MCPToolResult:
        query_extra = arguments.get("query", "")
        limit = min(int(arguments.get("limit") or 50), self._max_files)
        q_parts = [f"'{self._folder_id}' in parents", "trashed=false"]
        if query_extra:
            q_parts.append(f"({query_extra})")
        q = " and ".join(q_parts)
        params = {
            "q": q,
            "pageSize": limit,
            "fields": "files(id,name,mimeType,modifiedTime,size)",
        }
        token = await self._access_token()
        if token is None:
            return MCPToolResult.error(
                "google-auth is required for GoogleDriveConnector — install google-auth"
            )
        data = await self._drive_get("files", params, token)
        if "error" in data:
            return MCPToolResult.error("Google Drive request failed")
        return MCPToolResult.text(dumps_str(data.get("files", [])))

    async def _read_file(self, arguments: dict[str, Any]) -> MCPToolResult:
        file_id = arguments.get("file_id", "")
        if not file_id:
            return MCPToolResult.error("'file_id' argument is required")
        token = await self._access_token()
        if token is None:
            return MCPToolResult.error(
                "google-auth is required for GoogleDriveConnector — install google-auth"
            )
        # Get file metadata to determine MIME type
        meta = await self._drive_get(
            f"files/{file_id}", {"fields": "mimeType,name"}, token
        )
        if "error" in meta:
            return MCPToolResult.error("Google Drive request failed")
        mime = meta.get("mimeType", "")
        name = meta.get("name", file_id)
        export_mime = _EXPORT_TYPES.get(mime)
        if export_mime is not None:
            # Google Workspace file — export to plain text
            content = await self._drive_export(file_id, export_mime, token)
            return MCPToolResult.text(content)
        # Binary or regular file — return download link reference
        return MCPToolResult.text(
            dumps_str(
                {
                    "name": name,
                    "mimeType": mime,
                    "note": (
                        "Binary file — this connector is read-only text/export; "
                        "download via the Drive API (files/{id}?alt=media)"
                    ),
                }
            )
        )

    # ------------------------------------------------------------------
    # Credential helpers
    # ------------------------------------------------------------------

    async def _access_token(self) -> str | None:
        """Return a valid Bearer token, refreshing if necessary."""
        try:
            from google.auth.transport.requests import (  # type: ignore[import-not-found]
                Request,
            )
            from google.oauth2 import service_account  # type: ignore[import-not-found]
        except ImportError:
            return None
        if self._credentials is None:
            from quadkit.serialization import loads_str

            info = loads_str(self._sa_json)
            creds = service_account.Credentials.from_service_account_info(
                info, scopes=_SCOPES
            )
            if self._impersonated_email:
                creds = creds.with_subject(self._impersonated_email)
            self._credentials = creds
        creds = self._credentials
        if not creds.valid:
            # google-auth's refresh transport is blocking — keep the event
            # loop free by running it in a worker thread.
            await asyncio.to_thread(creds.refresh, Request())
        return creds.token

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    async def _drive_get(
        self, path: str, params: dict[str, Any], token: str
    ) -> dict[str, Any]:
        try:
            import aiohttp
        except ImportError:
            return {
                "error": {"message": "aiohttp is required for GoogleDriveConnector"}
            }
        headers = {"Authorization": f"Bearer {token}"}
        url = f"{_DRIVE_API}/{path}"
        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(
                    url, params=params, timeout=aiohttp.ClientTimeout(total=20)
                ) as resp:
                    data: dict[str, Any] = await resp.json(content_type=None)
                    logger.debug("drive_get", status=resp.status)
                    return data
        except (aiohttp.ClientError, ValueError) as exc:
            error_type = type(exc).__name__
            logger.warning("drive_get_failed", error_type=error_type)
            return {"error": {"message": f"Drive request failed ({error_type})"}}

    async def _drive_export(self, file_id: str, mime_type: str, token: str) -> str:
        try:
            import aiohttp
        except ImportError:
            return ""
        headers = {"Authorization": f"Bearer {token}"}
        url = f"{_DRIVE_API}/files/{file_id}/export"
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(
                url,
                params={"mimeType": mime_type},
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status != 200:
                    return f"Export failed: HTTP {resp.status}"
                return await resp.text()


__all__ = ["GoogleDriveConnector"]
