import asyncio
import pytest
from quadkit.app.base import Application
from quadkit.contracts.core.config import Environment
from quadkit.web.config import WebConfig, RateLimitConfig
from quadkit.web.di.provider import WebProvider
from quadkit.web.routing.controllers import Controller
from quadkit.web import get


class DummyController(Controller):
    @get("/dummy/{item_id}")
    async def get_item(self):
        return {"id": "123"}


@pytest.mark.asyncio
async def test_openapi_routes_present():
    app = Application(name="test-app")

    async def _allow_all(request):
        return True

    web = WebProvider(
        web_config=WebConfig(
            rate_limit=RateLimitConfig(enabled=False),
            debug_routes=True,
        ),
        controllers=[DummyController],
        debug_routes_auth=_allow_all,
    )

    await web.register(app.container)
    await web.boot(app.container)

    assert web.starlette is not None

    paths = list(map(lambda r: r.path, web.starlette.routes))
    assert "/openapi.json" in paths
    assert "/docs" in paths
    assert "/dummy/{item_id}" in paths

    await web.shutdown()


def _production_config() -> WebConfig:
    """A production WebConfig that passes the production security guards."""
    from quadkit.validation import SecretStr
    from quadkit.web.security.config import CSRFConfig, SecurityConfig

    return WebConfig(
        env=Environment.PRODUCTION,
        security=SecurityConfig(
            csrf=CSRFConfig(enabled=True, secret_key=SecretStr("k")),
            allowed_hosts=["app.example.com"],
        ),
        rate_limit=RateLimitConfig(enabled=False),
    )


async def _mount(web: WebProvider, app: Application) -> list[str]:
    await web.register(app.container)
    await web.boot(app.container)
    assert web.starlette is not None
    paths = [route.path for route in web.starlette.routes]
    await web.shutdown()
    return paths


@pytest.mark.asyncio
async def test_docs_routes_withheld_in_production():
    """Production serves no schema until an operator opts in (S-02)."""
    app = Application(name="test-app")
    web = WebProvider(web_config=_production_config(), controllers=[DummyController])

    paths = await _mount(web, app)

    assert "/openapi.json" not in paths
    assert "/docs" not in paths
    assert "/redoc" not in paths
    assert "/docs-static" not in paths
    assert "/dummy/{item_id}" in paths


@pytest.mark.asyncio
async def test_docs_routes_served_when_production_opts_in():
    """web.api_docs.enabled=true publishes the schema in production."""
    from quadkit.web.config import APIDocsConfig

    config = _production_config()
    config.api_docs = APIDocsConfig(enabled=True)
    app = Application(name="test-app")
    web = WebProvider(web_config=config, controllers=[DummyController])

    paths = await _mount(web, app)

    assert "/openapi.json" in paths
    assert "/docs" in paths
    assert "/redoc" in paths


@pytest.mark.asyncio
async def test_docs_routes_withheld_when_disabled():
    """web.api_docs.enabled=false withholds the routes outside production too."""
    from quadkit.web.config import APIDocsConfig

    config = WebConfig(
        api_docs=APIDocsConfig(enabled=False),
        rate_limit=RateLimitConfig(enabled=False),
    )
    app = Application(name="test-app")
    web = WebProvider(web_config=config, controllers=[DummyController])

    paths = await _mount(web, app)

    assert "/openapi.json" not in paths
    assert "/docs" not in paths
    assert "/redoc" not in paths
