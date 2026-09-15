import pytest
from typing import Any
from unittest.mock import MagicMock, AsyncMock
import inspect
from dataclasses import dataclass

from quadkit.web.routing.parameter_binder import ParameterBinder
from quadkit.web.routing.execution_context import WebExecutionContext
from quadkit.web.routing.parameters import query, path, body
from quadkit.web.pipes.builtin.parse import ParseIntPipe
from quadkit.web.pipes.decorators import use_pipes
from quadkit.web.protocols import PipeProtocol, ParamMetadata
from quadkit.domain import DomainModel

class MultiplyPipe(PipeProtocol):
    def __init__(self, factor: int = 2):
        self.factor = factor
    async def transform(self, value: Any, metadata: ParamMetadata) -> int:
        return int(value) * self.factor

@pytest.mark.asyncio
class TestPipeIntegration:
    async def test_parameter_level_pipe(self):
        # Handler with a pipe on a parameter
        async def handler(age: int = query(pipes=[ParseIntPipe()])):
            return age

        # Mock context
        request = MagicMock()
        request.query_params = {"age": "25"}
        request.path_params = {}
        
        context = WebExecutionContext(
            request=request,
            handler=handler,
            container=None
        )

        sig = inspect.signature(handler)
        hints = {"age": int}
        binder = ParameterBinder(sig, hints)
        
        kwargs = await binder.bind(context)
        assert kwargs["age"] == 25
        assert isinstance(kwargs["age"], int)

    async def test_handler_level_pipe(self):
        # Handler with a pipe at the method level
        @use_pipes(MultiplyPipe(factor=3))
        async def handler(count: int = query()):
            return count

        # Mock context
        request = MagicMock()
        request.query_params = {"count": "10"}
        request.path_params = {}
        
        context = WebExecutionContext(
            request=request,
            handler=handler,
            container=None
        )

        sig = inspect.signature(handler)
        hints = {"count": int}
        binder = ParameterBinder(sig, hints)
        
        kwargs = await binder.bind(context)
        # MultiplyPipe(3) transforms "10" to 30
        assert kwargs["count"] == 30

    async def test_multiple_pipes_chaining(self):
        # Chaining ParseIntPipe and MultiplyPipe
        async def handler(val: int = query(pipes=[ParseIntPipe(), MultiplyPipe(10)])):
            return val

        request = MagicMock()
        request.query_params = {"val": "5"}
        request.path_params = {}
        
        context = WebExecutionContext(request=request, handler=handler, container=None)
        binder = ParameterBinder(inspect.signature(handler), {"val": int})
        
        kwargs = await binder.bind(context)
        # "5" -> 5 -> 50
        assert kwargs["val"] == 50

    async def test_pipe_validation_error(self):
        # ParseIntPipe should raise ValueError for invalid strings
        async def handler(age: int = query(pipes=[ParseIntPipe()])):
            return age

        request = MagicMock()
        request.query_params = {"age": "not-an-int"}
        request.path_params = {}
        
        context = WebExecutionContext(request=request, handler=handler, container=None)
        binder = ParameterBinder(inspect.signature(handler), {"age": int})
        
        with pytest.raises(ValueError, match="Invalid integer"):
            await binder.bind(context)

    async def test_validation_pipe_pydantic_error(self):
        # ValidationPipe should raise quadkit.contracts.exceptions.domain.ValidationError
        from quadkit.contracts.exceptions.domain import ValidationError
        from quadkit.web.pipes.builtin.validation import ValidationPipe
        
        @dataclass(init=False)
        class User(DomainModel):
            name: str
            age: int

        async def handler(user: User = body(pipes=[ValidationPipe(User)])):
            return user

        request = MagicMock()
        # Missing age
        request.json = AsyncMock(return_value={"name": "Bob"})
        request.query_params = {}
        request.path_params = {}
        
        context = WebExecutionContext(request=request, handler=handler, container=None)
        binder = ParameterBinder(inspect.signature(handler), {"user": User})
        
        with pytest.raises(ValidationError) as exc_info:
            await binder.bind(context)
        
        errors = exc_info.value.errors
        assert len(errors) > 0
        # Age should be missing (pydantic loc might be different depending on v1/v2, 
        # but unified binder maps it)
        assert any("age" in e.field for e in errors)
