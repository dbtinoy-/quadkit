import pytest
from quadkit.web import Controller, get, post, header, cookie, form, query, WebProvider
from quadkit.app import Application
from quadkit.testing.fixtures.bed import TestEnvironment
from quadkit.web.config import WebConfig, RateLimitConfig, SecurityConfig, CSRFConfig

class ParameterController(Controller):
    @get("/all-sources/{p}")
    async def get_all(
        self,
        p: str,
        q: str,
        h: str = header(alias="X-Custom-Header"),
        c: str = cookie(alias="session_id")
    ):
        return {
            "path": p,
            "query": q,
            "header": h,
            "cookie": c
        }

    @post("/form-data")
    async def post_form(
        self,
        username: str = form(),
        dept: str = form(alias="department", default="engineering")
    ):
        return {
            "username": username,
            "department": dept
        }

    @post("/mixed-body")
    async def post_mixed(
        self,
        q: str,
        h: str = header(alias="X-API-Key"),
        data: dict = None # Should come from JSON body
    ):
        return {
            "query": q,
            "header": h,
            "body": data
        }

    @get("/precedence")
    async def get_precedence(
        self,
        q: str = query(),
        h: str = header(alias="X-Value"),
    ):
        return {
            "q": q,
            "h": h
        }

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
    env.use_provider(WebProvider(web_config=config, controllers=[ParameterController]))
    
    async with env.context():
        from httpx import ASGITransport, AsyncClient
        # Get the starlette app from WebProvider
        web_provider = env.get_provider("web")
        starlette_app = web_provider.starlette
        async with AsyncClient(transport=ASGITransport(app=starlette_app), base_url="http://test") as client:
            yield client

@pytest.mark.asyncio
async def test_header_and_cookie_extraction(web_client):
    headers = {"X-Custom-Header": "header-val"}
    cookies = {"session_id": "cookie-val"}
    
    response = await web_client.get(
        "/all-sources/path-val?q=query-val",
        headers=headers,
        cookies=cookies
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["path"] == "path-val"
    assert data["query"] == "query-val"
    assert data["header"] == "header-val"
    assert data["cookie"] == "cookie-val"

@pytest.mark.asyncio
async def test_form_data_extraction(web_client):
    response = await web_client.post(
        "/form-data",
        data={"username": "alice", "department": "research"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "alice"
    assert data["department"] == "research"

@pytest.mark.asyncio
async def test_form_data_default_value(web_client):
    response = await web_client.post(
        "/form-data",
        data={"username": "bob"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "bob"
    assert data["department"] == "engineering"

@pytest.mark.asyncio
async def test_mixed_sources_with_body(web_client):
    response = await web_client.post(
        "/mixed-body?q=search",
        headers={"X-API-Key": "secret"},
        json={"key": "value"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["query"] == "search"
    assert data["header"] == "secret"
    assert data["body"] == {"key": "value"}

@pytest.mark.asyncio
async def test_source_precedence(web_client):
    response = await web_client.get(
        "/precedence?q=query-val",
        headers={"X-Value": "header-val"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["q"] == "query-val"
    assert data["h"] == "header-val"

@pytest.mark.asyncio
async def test_parameter_alias_case_insensitivity(web_client):
    # Headers are case-insensitive
    response = await web_client.get(
        "/all-sources/p?q=q",
        headers={"x-custom-header": "lowercase-header"},
        cookies={"session_id": "sid"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["header"] == "lowercase-header"
