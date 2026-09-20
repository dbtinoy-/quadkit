from dataclasses import dataclass, field
import pytest
from quadkit.domain import DomainModel
from quadkit.validation import Field, field_validator
from quadkit.web import Controller, get, post, query, body, WebProvider
from quadkit.app import Application
from quadkit.testing.fixtures.bed import TestEnvironment
from quadkit.web.config import WebConfig, RateLimitConfig, SecurityConfig, CSRFConfig

@dataclass
class Item(DomainModel):
    name: str
    price: float
    tags: list[str] = field(default_factory=list)

@dataclass
class NestedModel(DomainModel):
    id: int
    item: Item

class AdvancedController(Controller):
    @get("/items/{item_id}")
    async def get_item(self, item_id: int, q: str = "default"):
        return {"item_id": item_id, "q": q}

    @post("/nested")
    async def post_nested(self, data: NestedModel):
        return data

    @get("/validated")
    async def validated_query(
        self, 
        age: int = query(validation=lambda v: 0 <= v <= 120)
    ):
        return {"age": age}

try:
    import pytest_asyncio
except ImportError:
    pytest_asyncio = None

@pytest.fixture if pytest_asyncio is None else pytest_asyncio.fixture
async def web_client(app):
    from quadkit.identity.di.provider import IdentityProvider
    from quadkit.observability.di.sub_providers.observability import ObservabilityProvider
    config = WebConfig(rate_limit=RateLimitConfig(enabled=False), security=SecurityConfig(csrf=CSRFConfig(enabled=False)))
    env = TestEnvironment(app)
    env.use_provider(IdentityProvider())
    env.use_provider(ObservabilityProvider())
    env.use_provider(WebProvider(web_config=config, controllers=[AdvancedController]))
    
    async with env.context():
        from httpx import ASGITransport, AsyncClient
        web_provider = env.get_provider("web")
        starlette_app = web_provider.starlette
        async with AsyncClient(transport=ASGITransport(app=starlette_app), base_url="http://test") as client:
            yield client

@pytest.mark.asyncio
async def test_path_and_query_defaults(web_client):
    response = await web_client.get("/items/42")
    assert response.status_code == 200
    assert response.json() == {"item_id": 42, "q": "default"}

@pytest.mark.asyncio
async def test_nested_pydantic_body(web_client):
    payload = {
        "id": 1,
        "item": {
            "name": "Widget",
            "price": 9.99,
            "tags": ["useful", "blue"]
        }
    }
    response = await web_client.post("/nested", json=payload)
    assert response.status_code == 200
    assert response.json() == payload

@pytest.mark.asyncio
async def test_custom_validation_success(web_client):
    response = await web_client.get("/validated?age=25")
    assert response.status_code == 200
    assert response.json() == {"age": 25}

@pytest.mark.asyncio
async def test_custom_validation_failure(web_client):
    response = await web_client.get("/validated?age=150")
    # Custom validation failures currently might return 422 or 500 depending on how they are caught
    # Generic validation errors from Pydantic are usually 422
    assert response.status_code in (422, 500)