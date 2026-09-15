"""Transform interceptor for response transformation.

Allows transformation of handler responses before they're returned.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.web.protocols import (
    CallHandlerProtocol,
    ExecutionContextProtocol,
    WebInterceptorProtocol,
)

if TYPE_CHECKING:
    from collections.abc import Callable


class TransformInterceptor(WebInterceptorProtocol):
    """Interceptor that transforms handler responses.

    Can wrap, envelope, or restructure responses before they're returned.
    Useful for standardizing API response formats.

    Example:
        ```python
        # Wrap all responses in a standard envelope
        class EnvelopeInterceptor(TransformInterceptor):
            def transform(self, data: Any) -> dict:
                return {"success": True, "data": data}

        router.add_interceptor(EnvelopeInterceptor())
        ```
    """

    def __init__(
        self,
        transform: Callable[[Any], Any] | None = None,
        wrap_response: bool = False,
    ):
        """Initialize the transform interceptor.

        Args:
            transform: Optional custom transform function.
            wrap_response: If True, wraps response in a standard format.
        """
        self._transform = transform
        self._wrap_response = wrap_response

    async def intercept(
        self,
        context: ExecutionContextProtocol,
        next_handler: CallHandlerProtocol,
    ) -> Any:
        """Intercept and transform the response.

        Args:
            context: The execution context.
            next_handler: The next handler in the chain.

        Returns:
            Transformed response.
        """
        result = await next_handler.handle()

        # Apply transformation
        if self._transform:
            return self._transform(result)

        # Default wrap behavior
        if self._wrap_response:
            return self._wrap(result)

        return result

    def transform(self, data: Any) -> Any:
        """Transform the data.

        Override this in subclasses to provide custom transformation.

        Args:
            data: The data to transform.

        Returns:
            Transformed data.
        """
        return data

    def _wrap(self, data: Any) -> dict[str, Any]:
        """Wrap data in standard response format.

        Args:
            data: The data to wrap.

        Returns:
            Wrapped response.
        """
        return {
            "success": True,
            "data": data,
        }


__all__ = ["TransformInterceptor"]
