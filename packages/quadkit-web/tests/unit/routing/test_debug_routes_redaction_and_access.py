import asyncio
from starlette.testclient import TestClient

from quadkit.app.base import Application
from quadkit.web.config import WebConfig, WebProviderConfig, ServerConfig
from quadkit.web.di.provider import WebProvider
from quadkit.web.routing.controllers import Controller
from quadkit.web import get


class RedactController(Controller):
    @get("/secret/{id}")
    def s(self, id: int):
        return {"ok": True}


def test_debug_routes_redacted_in_production():
    app = Application(name="test-app")
    # debug_routes enabled, but server_config.debug remains False (production)
    web_config = WebConfig(debug_routes=True, server=ServerConfig(debug=False))

    async def _allow_all(request):
        return True

    web = WebProvider(
        controllers=[RedactController], web_config=web_config,
        debug_routes_auth=_allow_all,
    )

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(web.register(app.container))
        loop.run_until_complete(web.boot(app.container))

        client = TestClient(web.starlette)
        r = client.get("/debug/routes")
        assert r.status_code == 200
        j = r.json()
        assert "routes" in j
        # Ensure registered_file and registered_stack are redacted
        found = False
        for item in j["routes"]:
            if item.get("path") == "/secret/{id}":
                for origin in item.get("origins", []) + [item.get("registry_info", {})]:
                    if isinstance(origin, dict):
                        if "registered_file" in origin:
                            assert origin["registered_file"] == "<REDACTED>"
                        if "registered_stack" in origin and origin["registered_stack"]:
                            assert any(
                                "<REDACTED>" in e for e in origin["registered_stack"]
                            )
                found = True
        assert found

    finally:
        loop.run_until_complete(web.shutdown())
        loop.close()


def test_debug_routes_local_only_enforced():
    app = Application(name="test-app")
    web = WebProvider(
        controllers=[RedactController], provider_config=WebProviderConfig(debug_routes=True),
    )

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(web.register(app.container))
        loop.run_until_complete(web.boot(app.container))

        client = TestClient(web.starlette)
        # Remote client via X-Forwarded-For should be forbidden
        r = client.get("/debug/routes", headers={"X-Forwarded-For": "8.8.8.8"})
        assert r.status_code == 403

        # Local XFF allowed
        r2 = client.get("/debug/routes", headers={"X-Forwarded-For": "127.0.0.1"})
        assert r2.status_code == 200

    finally:
        loop.run_until_complete(web.shutdown())
        loop.close()


def test_debug_routes_middleware_gate():
    app = Application(name="test-app")
    # Require a middleware that is not present
    web = WebProvider(
        controllers=[RedactController],
        provider_config=WebProviderConfig(
            debug_routes=True, debug_routes_require_middleware="AdminGuard",
        ),
    )

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(web.register(app.container))
        loop.run_until_complete(web.boot(app.container))

        client = TestClient(web.starlette)
        r = client.get("/debug/routes")
        assert r.status_code == 404

        # Now provide the middleware and it should be available
        class AdminGuard:
            pass

        web2 = WebProvider(
            controllers=[RedactController],
            provider_config=WebProviderConfig(
                debug_routes=True, debug_routes_require_middleware="AdminGuard",
            ),
            middleware=[AdminGuard()],
        )
        try:
            loop.run_until_complete(web2.register(app.container))
            loop.run_until_complete(web2.boot(app.container))
            client2 = TestClient(web2.starlette)
            r2 = client2.get("/debug/routes")
            assert r2.status_code == 200
        finally:
            loop.run_until_complete(web2.shutdown())

    finally:
        loop.run_until_complete(web.shutdown())
        loop.close()
