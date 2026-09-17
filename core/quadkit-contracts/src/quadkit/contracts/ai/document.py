"""Document and Text Splitter contracts for Quadkit.

Defines Document and text splitting classes analogous to LangChain's.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Document:
    """A document (like LangChain's Document).

    Attributes:
        page_content: The text content.
        metadata: Additional metadata.
    """

    page_content: str
    metadata: dict[str, Any] = field(default_factory=dict)


class TextSplitter:
    """Base text splitter (like LangChain's TextSplitter).

    Splits text into chunks.
    """

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
    ) -> None:
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def split_text(self, text: str) -> list[str]:
        """Split text into chunks.

        Args:
            text: Text to split.

        Returns:
            List of text chunks.
        """
        if not text:
            return []

        chunks = []
        start = 0
        while start < len(text):
            end = start + self.chunk_size
            chunk = text[start:end]
            chunks.append(chunk)
            start += self.chunk_size - self.chunk_overlap

        return chunks


class RecursiveCharacterTextSplitter(TextSplitter):
    """Split by characters recursively (like LangChain's RecursiveCharacterTextSplitter)."""

    def __init__(
        self,
        separators: list[str] | None = None,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
    ) -> None:
        super().__init__(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        self.separators = separators or ["\n\n", "\n", " ", ""]

    def split_text(self, text: str) -> list[str]:
        """Split text recursively by separators."""
        if not text:
            return []

        final_chunks: list[str] = []
        for separator in self.separators:
            chunks = []
            if separator == "":
                chunks = list(text)
            else:
                parts = text.split(separator)
                for part in parts:
                    if part:
                        chunks.append(part)

            if len(chunks) > 1:
                break

        if not chunks:
            return [text]

        return self._merge_chunks(chunks)

    def _merge_chunks(self, chunks: list[str]) -> list[str]:
        """Merge chunks respecting size limits."""
        merged = []
        current = ""

        for chunk in chunks:
            if len(current) + len(chunk) <= self.chunk_size:
                current += chunk
            else:
                if current:
                    merged.append(current)
                current = chunk

        if current:
            merged.append(current)

        return merged


__all__ = [
    "Document",
    "RecursiveCharacterTextSplitter",
    "TextSplitter",
]
