import pytest
from unittest.mock import AsyncMock, MagicMock
from starlette.requests import Request
from quadkit.web.protocols import ExecutionContextProtocol
from quadkit.web.routing.parameter_binder import ParameterBinder
from quadkit.web.routing.execution_context import WebExecutionContext
from quadkit.domain import DomainModel
import inspect

from dataclasses import dataclass

@dataclass
class UserUpdate(DomainModel):
    name: str
    age: int

class TestParameterBinder:
    @pytest.fixture
    def mock_request(self):
        req = MagicMock(spec=Request)
        req.state = MagicMock()
        req.query_params = {}
        req.path_params = {}
        return req

    @pytest.mark.asyncio
    async def test_bind_path_params(self, mock_request):
        def handler(user_id: int):
            return user_id
            
        mock_request.path_params = {"user_id": 123}
        sig = inspect.signature(handler)
        
        context = WebExecutionContext(
            request=mock_request,
            handler=handler,
            route_metadata={"sig_info": {"sig": sig, "hints": {"user_id": int}}}
        )
        
        binder = ParameterBinder(sig, {"user_id": int})
        kwargs = await binder.bind(context)
        
        assert kwargs["user_id"] == 123

    @pytest.mark.asyncio
    async def test_bind_query_params(self, mock_request):
        def handler(q: str = "default"):
            return q
            
        mock_request.query_params = {"q": "search"}
        sig = inspect.signature(handler)
        
        context = WebExecutionContext(
            request=mock_request,
            handler=handler,
            route_metadata={"sig_info": {"sig": sig, "hints": {"q": str}}}
        )
        
        binder = ParameterBinder(sig, {"q": str})
        kwargs = await binder.bind(context)
        
        assert kwargs["q"] == "search"

    @pytest.mark.asyncio
    async def test_bind_di_service(self, mock_request):
        class MyService:
            pass
            
        def handler(svc: MyService):
            return svc
            
        service_instance = MyService()
        container = MagicMock()
        container.resolve = AsyncMock(return_value=service_instance)
        
        sig = inspect.signature(handler)
        context = WebExecutionContext(
            request=mock_request,
            handler=handler,
            container=container,
            route_metadata={"sig_info": {"sig": sig, "hints": {"svc": MyService}}}
        )
        
        binder = ParameterBinder(sig, {"svc": MyService})
        kwargs = await binder.bind(context)
        
        assert kwargs["svc"] is service_instance
        container.resolve.assert_awaited_once_with(MyService)

    @pytest.mark.asyncio
    async def test_bind_pydantic_model(self, mock_request):
        def handler(data: UserUpdate):
            return data
            
        mock_request.json = AsyncMock(return_value={"name": "Alice", "age": 30})
        
        sig = inspect.signature(handler)
        context = WebExecutionContext(
            request=mock_request,
            handler=handler,
            route_metadata={"sig_info": {"sig": sig, "hints": {"data": UserUpdate}}}
        )
        
        binder = ParameterBinder(sig, {"data": UserUpdate})
        kwargs = await binder.bind(context)
        
        assert isinstance(kwargs["data"], UserUpdate)
        assert kwargs["data"].name == "Alice"
        assert kwargs["data"].age == 30
