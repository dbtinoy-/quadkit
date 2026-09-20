import pytest
from quadkit import serialization as json
from unittest.mock import MagicMock
from starlette.requests import Request

from quadkit.web import JSONResponse, Response
from quadkit.result import Ok, Err
from quadkit.contracts.exceptions.domain import NotFoundError, ValidationError, FieldError
from quadkit.web.routing.pipeline import RequestPipeline
from quadkit.web.routing.execution_context import WebExecutionContext
from quadkit.web.serialization.serializers import ResponseSerializer
from quadkit.web.filters.builtin import DefaultExceptionFilter, ValidationErrorFilter

class TestSerialization:
    @pytest.mark.asyncio
    async def test_pipeline_serializes_dict(self):
        # Arrange
        async def handler():
            return {"foo": "bar"}
            
        mock_request = MagicMock(spec=Request)
        mock_request.query_params = {}
        mock_request.path_params = {}
        
        context = WebExecutionContext(
            request=mock_request,
            handler=handler,
            controller_class=None,
            method_name="test",
            route_metadata={},
            container=None
        )
        
        pipeline = RequestPipeline(filters=[DefaultExceptionFilter(), ValidationErrorFilter()])
        
        # Act
        result = await pipeline.execute(context)
        
        # Assert
        assert isinstance(result, JSONResponse)
        assert result.status_code == 200
        assert json.loads(result.body) == {"foo": "bar"}

    @pytest.mark.asyncio
    async def test_pipeline_serializes_ok_result(self):
        # Arrange
        async def handler():
            return Ok({"id": 123})
            
        mock_request = MagicMock(spec=Request)
        mock_request.query_params = {}
        mock_request.path_params = {}
        
        context = WebExecutionContext(
            request=mock_request,
            handler=handler,
            controller_class=None,
            method_name="test",
            route_metadata={},
            container=None
        )
        
        pipeline = RequestPipeline(filters=[DefaultExceptionFilter(), ValidationErrorFilter()])
        
        # Act
        result = await pipeline.execute(context)
        
        # Assert
        assert isinstance(result, JSONResponse)
        assert result.status_code == 200
        assert json.loads(result.body) == {"id": 123}

    @pytest.mark.asyncio
    async def test_pipeline_serializes_err_result_mapping_status(self):
        # Arrange
        async def handler():
            return Err(NotFoundError("User not found"))
            
        mock_request = MagicMock(spec=Request)
        mock_request.query_params = {}
        mock_request.path_params = {}
        
        context = WebExecutionContext(
            request=mock_request,
            handler=handler,
            controller_class=None,
            method_name="test",
            route_metadata={},
            container=None
        )
        
        pipeline = RequestPipeline(filters=[DefaultExceptionFilter(), ValidationErrorFilter()])
        
        # Act
        result = await pipeline.execute(context)
        
        # Assert
        assert isinstance(result, JSONResponse)
        assert result.status_code == 404
        data = json.loads(result.body)
        assert "User not found" in data["detail"]
        assert "not-found" in data["type"]

    @pytest.mark.asyncio
    async def test_pipeline_serializes_validation_error_with_details(self):
        # Arrange
        async def handler():
            err = ValidationError("Invalid data")
            err.add_error("name", "required", "value_error")
            return Err(err)
            
        mock_request = MagicMock(spec=Request)
        mock_request.query_params = {}
        mock_request.path_params = {}
        
        context = WebExecutionContext(
            request=mock_request,
            handler=handler,
            controller_class=None,
            method_name="test",
            route_metadata={},
            container=None
        )
        
        pipeline = RequestPipeline(filters=[DefaultExceptionFilter(), ValidationErrorFilter()])
        
        # Act
        result = await pipeline.execute(context)
        
        # Assert
        assert isinstance(result, JSONResponse)
        assert result.status_code == 422
        data = json.loads(result.body)
        details = data["errors"]
        assert len(details) == 1
        assert details[0]["field"] == "name"
        assert details[0]["message"] == "required"

    @pytest.mark.asyncio
    async def test_pipeline_preserves_explicit_response(self):
        # Arrange
        async def handler():
            return JSONResponse({"custom": "response"}, status_code=201)
            
        mock_request = MagicMock(spec=Request)
        mock_request.query_params = {}
        mock_request.path_params = {}
        
        context = WebExecutionContext(
            request=mock_request,
            handler=handler,
            controller_class=None,
            method_name="test",
            route_metadata={},
            container=None
        )
        
        pipeline = RequestPipeline(filters=[DefaultExceptionFilter(), ValidationErrorFilter()])
        
        # Act
        result = await pipeline.execute(context)
        
        # Assert
        assert isinstance(result, JSONResponse)
        assert result.status_code == 201
        assert json.loads(result.body) == {"custom": "response"}
