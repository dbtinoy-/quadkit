from __future__ import annotations

from rich.console import Console
from rich.theme import Theme

theme = Theme(
    {
        "info": "cyan",
        "warning": "yellow",
        "error": "bold red",
        "success": "bold green",
    },
)

console = Console(theme=theme)


__all__ = ["console"]
