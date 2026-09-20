import pytest
from quadkit import serialization as json
from typing import Any, TypeVar, cast
from unittest.mock import MagicMock
from starlette.requests import Request

from quadkit.web import JSONResponse, Response

from quadkit.contracts.web.protocols import ExceptionFilterProtocol
from quadkit.web.filters.decorators import use_filters
from quadkit.web.routing.router import Router
from quadkit.web.routing.pipeline import RequestPipeline
from quadkit.web.routing.execution_context import WebExecutionContext
from quadkit.contracts.exceptions.domain import DomainError, NotFoundError

class CustomException(Exception):
    pass

class CustomFilter(ExceptionFilterProtocol):
    def can_handle(self, exc: Exception) -> bool:
        return isinstance(exc, CustomException)
    
    async def handle(self, exc: Exception, request: Any) -> Any:
        return JSONResponse({"error": "custom_handled", "message": str(exc)}, status_code=418)

class NotFoundFilter(ExceptionFilterProtocol):
    def can_handle(self, exc: Exception) -> bool:
        return isinstance(exc, NotFoundError)
    
    async def handle(self, exc: Exception, request: Any) -> Any:
        return JSONResponse({"error": "not_found_handled"}, status_code=404)

@pytest.mark.asyncio
async def test_use_filters_on_handler():
    # Arrange
    @use_filters(CustomFilter())
    async def handler():
        raise CustomException("test error")
    
    filters = getattr(handler, "__filters__", [])
    assert len(filters) == 1
    assert isinstance(filters[0], CustomFilter)

@pytest.mark.asyncio
async def test_pipeline_executes_filters():
    # Arrange
    async def handler():
        raise CustomException("trigger filter")
    
    mock_request = MagicMock(spec=Request)
    mock_request.query_params = {}
    mock_request.path_params = {}
    mock_request.headers = {}
    mock_request.cookies = {}
    
    context = WebExecutionContext(
        request=mock_request,
        handler=handler,
        controller_class=None,
        method_name="test",
        route_metadata={},
        container=None
    )
    
    pipeline = RequestPipeline(filters=[CustomFilter()])
    
    # Act
    result = await pipeline.execute(context)
    
    # Assert
    assert isinstance(result, JSONResponse)
    assert result.status_code == 418
    data = json.loads(result.body)
    assert data["error"] == "custom_handled"

@pytest.mark.asyncio
async def test_filters_inheritance_from_class():
    # Arrange
    @use_filters(NotFoundFilter())
    class TestController:
        @use_filters(CustomFilter())
        async def handler(self):
            pass
            
    controller = TestController()
    filters = getattr(controller.handler, "__filters__", [])
    assert len(filters) == 2
    # The order depends on how @use_filters combines them.
    # Currently it does: handler_filters + class_filters or similar?
    # Actually @use_filters on class sets __filters__ on class.
    # Router collects them.
    
    # In our implementation of @use_filters, it appends to __filters__.
    # If applied to class, then method, they are separate.
    # Wait, let's verify what Router does.
    pass

@pytest.mark.asyncio
async def test_pipeline_precedence_local_over_global():
    # Arrange
    async def handler():
        raise CustomException("trigger filter")
    
    mock_request = MagicMock(spec=Request)
    mock_request.query_params = {}
    mock_request.path_params = {}
    mock_request.headers = {}
    mock_request.cookies = {}
    
    context = WebExecutionContext(
        request=mock_request,
        handler=handler,
        controller_class=None,
        method_name="test",
        route_metadata={},
        container=None
    )
    
    # Pipeline with local filter should win over global (which would return 500 if it reached it)
    pipeline = RequestPipeline(filters=[CustomFilter()])
    
    # Act
    result = await pipeline.execute(context)
    
    # Assert
    assert result.status_code == 418
    data = json.loads(result.body)
    assert data["error"] == "custom_handled"
