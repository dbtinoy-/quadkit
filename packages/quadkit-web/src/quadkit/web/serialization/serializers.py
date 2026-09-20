"""Response serializers for different media types."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from starlette.responses import HTMLResponse, JSONResponse, PlainTextResponse, Response

from quadkit.logging import get_logger
from quadkit.web.transport.responses import (
    HTMLResponse as QuadkitHTMLResponse,
)
from quadkit.web.transport.responses import (
    JSONResponse as QuadkitJSONResponse,
)

if TYPE_CHECKING:
    from starlette.requests import Request as StarletteRequest

    from quadkit.contracts.events import CommandBusProtocol, QueryBusProtocol
    from quadkit.contracts.mapping import ObjectMapperProtocol

logger = get_logger(__name__)


class AbstractMediaSerializer(ABC):
    """Protocol for media-specific response serializers."""

    @abstractmethod
    def supports(self, media_type: str) -> bool:
        """Check if this serializer supports the given media type."""
        ...

    @abstractmethod
    def supported_types(self) -> list[str]:
        """Return list of supported media types."""
        ...

    @abstractmethod
    async def serialize(
        self,
        data: Any,
        request: StarletteRequest,
        status_code: int = 200,
    ) -> Response:
        """Serialize data into a Response."""
        ...


class JSONSerializer(AbstractMediaSerializer):
    """Serializes responses as JSON using high-performance core utilities."""

    def supports(self, media_type: str) -> bool:
        return "application/json" in media_type

    def supported_types(self) -> list[str]:
        return ["application/json"]

    async def serialize(
        self,
        data: Any,
        request: StarletteRequest,
        status_code: int = 200,
    ) -> JSONResponse:
        # quadkit.web.transport.responses.JSONResponse handles high-performance
        # serialization (orjson/Pydantic) via core quadkit.serialization.
        # Bound at module import — this runs once per response.
        return QuadkitJSONResponse(content=data, status_code=status_code)  # type: ignore[return-value]


class HTMLSerializer(AbstractMediaSerializer):
    """Serializes responses as HTML."""

    def supports(self, media_type: str) -> bool:
        return "text/html" in media_type

    def supported_types(self) -> list[str]:
        return ["text/html"]

    async def serialize(
        self,
        data: Any,
        request: StarletteRequest,
        status_code: int = 200,
    ) -> HTMLResponse:
        # Bound at module import — this runs once per response.
        # Convert to string if not already
        if not isinstance(data, str):
            data = str(data)

        return QuadkitHTMLResponse(content=data, status_code=status_code)  # type: ignore[return-value]


class PlainTextSerializer(AbstractMediaSerializer):
    """Serializes responses as plain text."""

    def supports(self, media_type: str) -> bool:
        return "text/plain" in media_type

    def supported_types(self) -> list[str]:
        return ["text/plain"]

    async def serialize(
        self,
        data: Any,
        request: StarletteRequest,
        status_code: int = 200,
    ) -> PlainTextResponse:
        # Convert to string if not already
        if not isinstance(data, str):
            data = str(data)

        return PlainTextResponse(content=data, status_code=status_code)


class XMLSerializer(AbstractMediaSerializer):
    """Serializes responses as XML."""

    def supports(self, media_type: str) -> bool:
        return "application/xml" in media_type or "text/xml" in media_type

    def supported_types(self) -> list[str]:
        return ["application/xml", "text/xml"]

    async def serialize(
        self,
        data: Any,
        request: StarletteRequest,
        status_code: int = 200,
    ) -> Response:
        # Convert to string if not already
        if not isinstance(data, str):
            data = str(data)

        return Response(
            content=data, status_code=status_code, media_type="application/xml"
        )


class ResponseSerializer:
    """High-level orchestrator for response serialization.

    Handles:
    1. Result types (Ok/Err)
    2. CQRS Messages (Command/Query)
    3. ObjectMapper transformations
    4. Media-type specific serialization

    Dependencies are injected via constructor to avoid service locator pattern.
    """

    _registry: dict[str, AbstractMediaSerializer] = {}
    _default_serializer: AbstractMediaSerializer = JSONSerializer()

    def __init__(
        self,
        command_bus: CommandBusProtocol | None = None,
        query_bus: QueryBusProtocol | None = None,
        mapper: ObjectMapperProtocol | None = None,
    ) -> None:
        """Initialize the serializer with optional injected dependencies.

        Args:
            command_bus: Optional CommandBusProtocol for dispatching commands.
            query_bus: Optional QueryBusProtocol for executing queries.
            mapper: Optional ObjectMapperProtocol for transformations.
        """
        self.command_bus = command_bus
        self.query_bus = query_bus
        self.mapper = mapper

    @classmethod
    def _get_registry(cls) -> dict[str, AbstractMediaSerializer]:
        if not cls._registry:
            # Initialize registry
            serializers = [
                JSONSerializer(),
                HTMLSerializer(),
                PlainTextSerializer(),
                XMLSerializer(),
            ]
            for serializer in serializers:
                for mime in serializer.supported_types():
                    cls._registry[mime.lower()] = serializer
        return cls._registry

    @classmethod
    def negotiate(cls, accept_header: str | None) -> AbstractMediaSerializer:
        """Negotiate the best serializer based on the Accept header."""
        if not accept_header:
            return cls._default_serializer

        registry = cls._get_registry()
        for part in accept_header.split(","):
            mime = part.split(";")[0].strip().lower()
            if mime in registry:
                return registry[mime]
            if mime == "*/*":
                return cls._default_serializer

        return cls._default_serializer

    async def serialize(
        self,
        result: Any,
        request: StarletteRequest,
        route: Any = None,
    ) -> Response:
        """Standardize handler result into a Starlette-compatible Response.

        Uses injected dependencies instead of service locator pattern.
        """
        from quadkit.result import Result
        from quadkit.web.transport.responses import HTMLContent, JSONResponse

        # 0. Handle None → 204 No Content
        # (Status code from decorator is ignored for None, as 204 is semantic for NO content)
        if result is None:
            return Response(status_code=204)

        # Extract status code from route metadata if available
        status_code = 200
        if route and hasattr(route, "metadata") and isinstance(route.metadata, dict):
            status_code = route.metadata.get("status_code", 200)
        elif isinstance(route, dict):
            status_code = route.get("status_code", 200)

        # 1. Handle explicit Response
        if isinstance(result, Response):
            return result

        # 1.5 Handle bytes directly
        if isinstance(result, (bytes, bytearray)):
            return Response(content=result, media_type="application/octet-stream")

        # 1.6 Handle HTMLContent marker (check before bare str since HTMLContent is str subclass)
        if isinstance(result, HTMLContent):
            from quadkit.web.transport.responses import HTMLResponse

            return HTMLResponse(content=str(result))

        # 1.7 Handle bare strings as HTML (HTMX-friendly)
        if isinstance(result, str):
            return Response(content=result, media_type="text/html")

        # 2. Handle Result Object
        if isinstance(result, Result):
            if result.is_ok():
                result = result.unwrap()
                # An Ok that wraps a ready-made Response passes through
                # untouched (cookie-setting endpoints need this).
                if isinstance(result, Response):
                    return result
                # Continue to normal serialization for the inner value
            else:
                # Let the DomainExceptionFilter handle the error by raising it
                # UNLESS it's an HTTPError we want to return directly.
                from quadkit.web.exceptions import HTTPError

                error = result.unwrap_err()
                if isinstance(error, HTTPError):
                    return JSONResponse(
                        content={
                            "error": error.code,
                            "message": error.detail,
                            "details": error.details,
                        },
                        status_code=error.status_code,
                    )
                from quadkit.web.routing.result_bridge import ResultResponseMapper

                return ResultResponseMapper.error_to_response(error)

        # 3. Handle CQRS Messages (Command/Query)
        from quadkit.contracts.events.messages import Command, Query

        if isinstance(result, (Command, Query)):
            try:
                if isinstance(result, Command):
                    if not self.command_bus:
                        raise ValueError("CommandBusProtocol not injected")
                    result = await self.command_bus.dispatch(result)
                else:
                    if not self.query_bus:
                        raise ValueError("QueryBusProtocol not injected")
                    result = await self.query_bus.execute(result)

                # Recursively serialize the bus result
                return await self.serialize(result, request, route)
            except Exception as e:  # noqa: BLE001 — bus dispatch may raise from user-defined command/query handlers; normalise to InternalServerError
                from quadkit.web.exceptions import InternalServerError

                logger.exception("Bus dispatch failed")
                raise InternalServerError(f"Dispatch error: {e}") from e

        # 4. Handle ObjectMapper Transformation
        if (
            route
            and hasattr(route, "metadata")
            and "response_model" in route.metadata
            and result is not None
            and self.mapper
        ):
            response_model = route.metadata["response_model"]
            try:
                if self.mapper:
                    result = self.mapper.map(result, response_model)
            except (LookupError, RuntimeError, AttributeError):
                logger.debug("Mapping failed for %s", response_model)

        # 5.5. Coerce DomainModel → dict for uniform JSON serialization
        try:
            from quadkit.contracts.domain.base import (  # type: ignore[attr-defined]
                DomainModel,
            )

            if isinstance(result, DomainModel):
                result = (
                    result.model_dump()
                    if hasattr(result, "model_dump")
                    else vars(result)
                )
        except ImportError:
            pass

        # 6. Delegate to media-specific serializers based on Accept header
        accept = request.headers.get("accept")
        serializer = self.negotiate(accept)
        return await serializer.serialize(result, request, status_code=status_code)
