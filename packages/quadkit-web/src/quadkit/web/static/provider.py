from __future__ import annotations


class StaticFileProvider:
    """Provider for static file serving configuration."""

    def __init__(
        self,
        directory: str = "static",
        prefix: str = "/static",
        html: bool = False,
    ) -> None:
        self.directory = directory
        self.prefix = prefix
        self.html = html

    def create_middleware(self) -> dict:
        """Create the static files middleware configuration."""
        return {
            "directory": self.directory,
            "prefix": self.prefix,
            "html": self.html,
        }
