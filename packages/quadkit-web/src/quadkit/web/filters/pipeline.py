"""Filter pipeline execution for exception handling.

Provides production-grade exception filter pipeline with DI integration.
"""

from __future__ import annotations

import traceback
from typing import Any, cast

from quadkit.contracts.web.protocols import ExceptionFilterProtocol
from quadkit.logging import get_logger
from quadkit.web.transport.responses import JSONResponse, Response

logger = get_logger(__name__)


class FilterPipeline:
    """Production-grade exception filter pipeline with DI integration.

    Provides:
    - add_filter() with O(1) index by exception type
    - remove_filter() to remove filters by type
    - MRO-based exception matching for subclass support
    - Fallback to default 500 response
    """

    def __init__(
        self, filters: list[ExceptionFilterProtocol] | None = None, debug: bool = False
    ):
        """Initialize the filter pipeline.

        Args:
            filters: Optional list of initial filters.
            debug: When ``True``, unhandled exceptions render an HTML debug
                page for browser clients instead of a generic JSON 500.
        """
        self._filters: list[ExceptionFilterProtocol] = list(filters) if filters else []
        self._debug = debug
        # Type index for O(1) lookup by exact exception type
        self._type_index: dict[type[Exception], ExceptionFilterProtocol] = {}
        # Rebuild index on init
        self._rebuild_index()

    def _rebuild_index(self) -> None:
        """Rebuild the type index from filters."""
        self._type_index.clear()
        for f in self._filters:
            if hasattr(f, "exception_type"):
                self._type_index[f.exception_type] = f

    @property
    def filters(self) -> list[ExceptionFilterProtocol]:
        """Get all registered filters."""
        return list(self._filters)

    def add_filter(self, filter_instance: ExceptionFilterProtocol) -> None:
        """Add filter and index by exception type for O(1) lookup.

        Args:
            filter_instance: The filter to add.
        """
        if filter_instance not in self._filters:
            self._filters.append(filter_instance)

            # Index by exception type if available
            if hasattr(filter_instance, "exception_type"):
                self._type_index[filter_instance.exception_type] = filter_instance

    def remove_filter(self, filter_type: type[ExceptionFilterProtocol]) -> None:
        """Remove filter by type.

        Args:
            filter_type: The type of filter to remove.
        """
        self._filters = [
            f
            for f in self._filters
            if not (isinstance(f, filter_type) or type(f) is filter_type)
        ]
        # Rebuild index
        self._rebuild_index()

    def clear(self) -> None:
        """Clear all filters.

        Use in tests only to prevent test pollution between test cases.
        """
        self._filters.clear()
        self._rebuild_index()

    def can_handle(self, exc: Exception) -> bool:
        """Report whether a registered filter claims this exception.

        Mirrors :meth:`handle`'s matching order (exact type, MRO walk,
        filter-level predicate) without running any handler, so a caller can
        pick between two pipelines before executing either one.

        Args:
            exc: The exception to match.

        Returns:
            True when at least one registered filter can handle ``exc``.
        """
        exc_type = type(exc)
        if exc_type in self._type_index:
            return True
        for klass in exc_type.__mro__:
            if klass in self._type_index:
                return True
        return any(f.can_handle(exc) for f in self._filters)

    async def handle(self, exc: Exception, request: Any) -> Response:
        """Find matching filter via MRO walk for exception subclass support.

        Args:
            exc: The exception that was raised.
            request: The HTTP request.

        Returns:
            Response from the matching filter, or default 500.
        """
        # Try exact type match first
        exc_type = type(exc)
        if exc_type in self._type_index:
            return cast(
                "Response",
                await cast("Any", self._type_index[exc_type]).handle(exc, request),
            )

        # Walk MRO for subclass matching
        for klass in exc_type.__mro__:
            if klass in self._type_index:
                return cast(
                    "Response",
                    await cast("Any", self._type_index[klass]).handle(exc, request),
                )

        # Try filter-level matching (last added runs first)
        for f in reversed(self._filters):
            if f.can_handle(exc):
                return cast("Response", await cast("Any", f).handle(exc, request))

        # Default: structured 500 response (HTML in debug mode for browsers)
        logger.error(
            "unhandled_exception_in_filter_pipeline",
            error=str(exc),
            error_type=type(exc).__name__,
        )

        if self._debug:
            from quadkit.web.errors.html_error_renderer import DebugHtmlErrorRenderer

            renderer = DebugHtmlErrorRenderer()
            if renderer.should_render(request):
                return renderer.render(exc, request, status_code=500)  # type: ignore[return-value]

        # The last-resort response uses the same RFC 7807 media type as every
        # other filter: a client that keys on `application/problem+json` sees
        # a 500 like any other failure. Debug adds the exception type and
        # traceback as problem extensions; `is_debug_mode()` is env-gated
        # (`QK_DEBUG`), so a production app never reaches this branch.
        from quadkit.web.errors.problem_detail import ProblemDetail

        problem = ProblemDetail.internal_error(
            detail=str(exc) if self._debug else "An unexpected error occurred",
        )
        content = problem.to_dict()
        if self._debug:
            content["exception_type"] = type(exc).__name__
            content["traceback"] = traceback.format_exc()
        return JSONResponse(
            content=content,
            status_code=500,
            media_type="application/problem+json",
        )


__all__ = ["FilterPipeline"]
