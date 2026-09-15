"""Document loader protocols and exceptions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from quadkit.contracts.ai.vector import Document
    from quadkit.contracts.core.result import Result

from quadkit.contracts.ai.exceptions import RAGError


class LoaderError(RAGError):
    """Raised when document loading fails in an expected, recoverable way.

    Extended in quadkit-ai-rag with specific failures like unsupported
    format, parse errors, network failures, etc.
    """

    _code = "QK_ERR_LOAD_001"

    def __init__(self, message: str = "Loader error", **kwargs: Any) -> None:
        super().__init__(message, **kwargs)


@runtime_checkable
class DocumentLoaderProtocol(Protocol):
    """Protocol for document loaders.

    Implementations load documents from various sources (files, URLs,
    databases) and return them as Document objects.
    """

    async def load(
        self, source: str, **kwargs: Any
    ) -> Result[list[Document], LoaderError]:
        """Load documents from a source.

        Args:
            source: File path, URL, or other source identifier.
            **kwargs: Loader-specific parameters.

        Returns:
            Ok(list of Document) on success.
            Err(LoaderError) on failure.
        """
        ...


@runtime_checkable
class LoaderRegistryProtocol(Protocol):
    """Protocol for a registry that maps sources to loaders.

    Implementations maintain a mapping of source types (file extensions,
    URL schemes) to loader instances. Used for auto-detection and
    on-demand loader resolution.
    """

    def register(self, schemes: list[str], loader: DocumentLoaderProtocol) -> None:
        """Register a loader for one or more source schemes.

        Args:
            schemes: List of file extensions (e.g. [".pdf"]) or URL schemes.
            loader: DocumentLoaderProtocol instance to handle those schemes.
        """
        ...

    def get(self, source: str) -> DocumentLoaderProtocol | None:
        """Get the loader for a source, or None if not registered.

        Args:
            source: File path or URL.

        Returns:
            The registered loader, or None if no match found.
        """
        ...

    def list(self) -> list[str]:
        """List all registered source schemes.

        Returns:
            List of registered scheme strings.
        """
        ...


__all__ = [
    "DocumentLoaderProtocol",
    "LoaderError",
    "LoaderRegistryProtocol",
]
