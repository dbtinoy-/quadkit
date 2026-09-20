from starlette.testclient import TestClient
from quadkit.app.base import Application
from quadkit.web.config import WebConfig, RateLimitConfig
from quadkit.web.di.provider import WebProvider
from quadkit.web.routing.controllers import Controller
from quadkit.web import get


class Service:
    def __init__(self):
        self.value = "injected"


class DepController(Controller):
    @get("/dep")
    async def use(self, svc: Service):
        return {"value": svc.value}


def test_di_dependency_injection():
    # Disable rate limiting to avoid requiring RateLimitProvider
    rate_limit_config = RateLimitConfig(enabled=False)
    web_config = WebConfig(rate_limit=rate_limit_config)
    
    app = Application(name="test-app")
    # Register a singleton service in the app container
    app.container.singleton(Service, Service())

    web = WebProvider(controllers=[DepController], web_config=web_config)

    import asyncio

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(web.register(app.container))
        loop.run_until_complete(web.boot(app.container))

        client = TestClient(web.starlette)
        r = client.get("/dep")
        assert r.status_code == 200
        assert r.json()["value"] == "injected"

    finally:
        loop.run_until_complete(web.shutdown())
        loop.close()
