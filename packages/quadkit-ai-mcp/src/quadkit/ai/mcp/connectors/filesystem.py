"""Sandboxed filesystem connector — exposes read/write/list/search via MCP.

All path operations are strictly sandboxed to the configured ``root_dir``.
Any attempt to escape the sandbox via ``..`` traversal, symlinks outside
the root, or absolute paths is rejected with an error result.

Tools exposed:
- ``read_file``      — Read text content of a file
- ``write_file``     — Write text content to a file (disabled when read_only)
- ``list_directory`` — List files and subdirectories
- ``search_files``   — Search for files matching a glob pattern
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from quadkit.ai.mcp.types import MCPResource, MCPToolDefinition, MCPToolResult
from quadkit.logging import (
    get_logger,
)

logger = get_logger(__name__)

_MAX_FILE_READ_BYTES = 1 * 1024 * 1024  # 1 MB default


class FilesystemConnector:
    """Sandboxed filesystem access via MCP tools and resources.

    All file I/O is restricted to *root_dir*. Any path that resolves outside
    the sandbox is rejected with a descriptive error.

    Tools: ``read_file``, ``write_file``, ``list_directory``, ``search_files``
    Resources: ``file://{path}`` for files within the sandbox

    Example::

        connector = FilesystemConnector(root_dir="/data/docs")
        # Register with MCPProvider controllers or a custom registry
    """

    def __init__(
        self,
        root_dir: str,
        *,
        read_only: bool = False,
        max_read_bytes: int = _MAX_FILE_READ_BYTES,
    ) -> None:
        """Initialize the filesystem connector.

        Args:
            root_dir: Root directory for sandboxed operations.
            read_only: Disables ``write_file`` when True.
            max_read_bytes: Maximum bytes to read from a file (default 1 MB).

        Raises:
            ValueError: If ``root_dir`` is empty or does not exist.
        """
        if not root_dir:
            raise ValueError("FilesystemConnector requires a non-empty root_dir")
        resolved = Path(root_dir).resolve()
        if not resolved.exists():
            raise ValueError(f"FilesystemConnector root_dir does not exist: {resolved}")
        self._root = resolved
        self._read_only = read_only
        self._max_read_bytes = max_read_bytes

    # ------------------------------------------------------------------
    # MCPToolProviderProtocol interface
    # ------------------------------------------------------------------

    async def list_tools(self) -> list[dict[str, Any]]:
        """Return tool definitions for this connector."""
        tools = [
            MCPToolDefinition(
                name="read_file",
                description="Read the text content of a file within the sandbox",
                input_schema={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Relative path to the file",
                        }
                    },
                    "required": ["path"],
                },
            ).to_dict(),
            MCPToolDefinition(
                name="list_directory",
                description="List files and subdirectories at a path",
                input_schema={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Relative directory path (empty for root)",
                            "default": "",
                        }
                    },
                },
            ).to_dict(),
            MCPToolDefinition(
                name="search_files",
                description="Search for files matching a glob pattern",
                input_schema={
                    "type": "object",
                    "properties": {
                        "pattern": {
                            "type": "string",
                            "description": "Glob pattern (e.g. '**/*.py')",
                        }
                    },
                    "required": ["pattern"],
                },
            ).to_dict(),
        ]
        if not self._read_only:
            tools.append(
                MCPToolDefinition(
                    name="write_file",
                    description="Write text content to a file within the sandbox",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "Relative path to the file",
                            },
                            "content": {
                                "type": "string",
                                "description": "Text content to write",
                            },
                        },
                        "required": ["path", "content"],
                    },
                ).to_dict()
            )
        return tools

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> MCPToolResult:
        """Dispatch tool calls to handler methods.

        Args:
            name: Tool name.
            arguments: Tool arguments.

        Returns:
            MCPToolResult with text content or error.
        """
        from quadkit.contracts.mcp.exceptions import MCPToolCallError

        dispatch = {
            "read_file": self._read_file,
            "write_file": self._write_file,
            "list_directory": self._list_directory,
            "search_files": self._search_files,
        }
        handler = dispatch.get(name)
        if handler is None:
            raise MCPToolCallError(
                message=f"Unknown filesystem tool: {name}", tool_name=name
            )
        return await handler(arguments)

    # ------------------------------------------------------------------
    # MCPResourceProviderProtocol interface
    # ------------------------------------------------------------------

    async def list_resources(self) -> list[dict[str, Any]]:
        """List all files in the sandbox root as MCP resources.

        Symlinks that resolve *outside* the sandbox are skipped so the
        resource listing never advertises files the sandbox refuses.
        """
        resources = []
        for path in self._root.rglob("*"):
            if path.is_file() and self._is_within_sandbox(path.resolve()):
                rel = path.relative_to(self._root)
                resources.append(
                    MCPResource(
                        uri=f"file://{rel}",
                        name=str(rel),
                        description=f"File: {rel}",
                        mime_type=_guess_mime(str(rel)),
                    ).to_dict()
                )
        return resources

    async def read_resource(self, uri: str) -> dict[str, Any]:
        """Read a file resource by URI.

        Args:
            uri: ``file://relative/path`` URI.

        Returns:
            MCP resource content dict.
        """
        rel = uri.removeprefix("file://")
        result = await self._read_file({"path": rel})
        text = result.content[0]["text"] if result.content else ""
        return {"contents": [{"uri": uri, "mimeType": _guess_mime(rel), "text": text}]}

    # ------------------------------------------------------------------
    # Tool implementations
    # ------------------------------------------------------------------

    async def _read_file(self, arguments: dict[str, Any]) -> MCPToolResult:
        path_str = arguments.get("path", "")
        resolved = self._resolve_path(path_str)
        if resolved is None:
            return MCPToolResult.error("Access denied: path is outside sandbox")
        if not resolved.exists():
            return MCPToolResult.error("File not found")
        if not resolved.is_file():
            return MCPToolResult.error("Not a file")
        try:
            size = resolved.stat().st_size
            if size > self._max_read_bytes:
                return MCPToolResult.error(
                    f"File too large ({size} bytes). Maximum is {self._max_read_bytes} bytes."
                )
            return MCPToolResult.text(
                resolved.read_text(encoding="utf-8", errors="replace")
            )
        except Exception as exc:  # noqa: BLE001 — filesystem boundary
            error_type = type(exc).__name__
            logger.warning("filesystem_read_error", error_type=error_type)
            return MCPToolResult.error(f"Cannot read file ({error_type})")

    async def _write_file(self, arguments: dict[str, Any]) -> MCPToolResult:
        if self._read_only:
            return MCPToolResult.error("Connector is read-only")
        path_str = arguments.get("path", "")
        content = arguments.get("content", "")
        resolved = self._resolve_path(path_str)
        if resolved is None:
            return MCPToolResult.error("Access denied: path is outside sandbox")
        try:
            resolved.parent.mkdir(parents=True, exist_ok=True)
            resolved.write_text(content, encoding="utf-8")
            return MCPToolResult.text(f"Written {len(content)} chars to {path_str}")
        except Exception as exc:  # noqa: BLE001 — filesystem boundary
            error_type = type(exc).__name__
            logger.warning("filesystem_write_error", error_type=error_type)
            return MCPToolResult.error(f"Cannot write file ({error_type})")

    async def _list_directory(self, arguments: dict[str, Any]) -> MCPToolResult:
        path_str = arguments.get("path", "") or ""
        resolved = self._resolve_path(path_str) if path_str else self._root
        if resolved is None:
            return MCPToolResult.error("Access denied: path is outside sandbox")
        if not resolved.exists():
            return MCPToolResult.error("Directory not found")
        if not resolved.is_dir():
            return MCPToolResult.error("Not a directory")
        try:
            entries = []
            for entry in sorted(resolved.iterdir()):
                entries.append(f"[{'d' if entry.is_dir() else 'f'}] {entry.name}")
            return MCPToolResult.text("\n".join(entries) or "(empty)")
        except Exception as exc:  # noqa: BLE001 — filesystem boundary
            return MCPToolResult.error(f"Cannot list directory ({type(exc).__name__})")

    async def _search_files(self, arguments: dict[str, Any]) -> MCPToolResult:
        pattern = arguments.get("pattern", "*")
        try:
            matches = []
            for p in self._root.rglob(pattern):
                resolved = p.resolve()
                # Resolve first: a symlink whose target escapes the sandbox
                # must not show up in results (rglob paths are lexical).
                if p.is_file() and self._is_within_sandbox(resolved):
                    matches.append(str(p.relative_to(self._root)))
            return MCPToolResult.text("\n".join(sorted(matches)) or "No files matched")
        except Exception as exc:  # noqa: BLE001 — any search failure is a tool error result
            return MCPToolResult.error(f"Search failed ({type(exc).__name__})")

    # ------------------------------------------------------------------
    # Path helpers
    # ------------------------------------------------------------------

    def _resolve_path(self, path_str: str) -> Path | None:
        """Resolve *path_str* relative to root and check sandbox containment."""
        target = (self._root / path_str).resolve()
        if not self._is_within_sandbox(target):
            logger.warning("sandbox_escape_attempt")
            return None
        return target

    def _is_within_sandbox(self, path: Path) -> bool:
        """Return True if *path* is inside the sandbox root."""
        try:
            path.relative_to(self._root)
            return True
        except ValueError:
            return False


def _guess_mime(filename: str) -> str:
    """Return a best-guess MIME type from a filename."""
    _ext_map = {
        ".py": "text/x-python",
        ".json": "application/json",
        ".yaml": "application/yaml",
        ".yml": "application/yaml",
        ".md": "text/markdown",
        ".txt": "text/plain",
        ".html": "text/html",
        ".xml": "application/xml",
        ".csv": "text/csv",
        ".pdf": "application/pdf",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
    }
    ext = Path(filename).suffix.lower()
    return _ext_map.get(ext, "text/plain")


__all__ = ["FilesystemConnector"]
