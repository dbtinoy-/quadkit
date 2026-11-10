"""Regression tests for route-scoped SHA-256 CSP on GraphQL playground."""

from __future__ import annotations

from starlette.applications import Starlette
from starlette.testclient import TestClient

from quadkit.contracts.graphql.protocols import GraphQLPlaygroundProtocol
from quadkit.di.container import Container
from quadkit.web.config.top_level import WebConfig
from quadkit.web.integrations.graphql import GraphQLIntegration


class _StubPlayground:
    enabled = True
    page_path = "/graphql/playground"
    endpoint_path = "/graphql"
    title = "Test Playground"

    def render(self, endpoint: str) -> str:
        return (
            f"<!doctype html><html><body>"
            f'<script>const ENDPOINT = "{endpoint}";</script>'
            f"</body></html>"
        )


async def test_graphql_playground_emits_sha256_csp_without_unsafe_script_directives() -> (
    None
):
    """Playground HTML response pins inline script via sha256 hash instead of unsafe-inline."""
    app = Starlette()
    container = Container()
    container.singleton(GraphQLPlaygroundProtocol, _StubPlayground())
    container.singleton(
        WebConfig,
        WebConfig.model_validate(
            {
                "security": {
                    "csp": {
                        "enabled": True,
                        "directives": {"frame-ancestors": "*"},
                    }
                }
            }
        ),
    )

    integration = GraphQLIntegration()
    await integration._configure_playground(app, container)

    client = TestClient(app)
    res = client.get("/graphql/playground")
    assert res.status_code == 200
    csp = res.headers.get("content-security-policy", "")
    assert "script-src 'self' 'sha256-" in csp
    assert "script-src-elem 'self' 'sha256-" in csp
    assert "'unsafe-eval'" not in csp
    assert "script-src 'self' 'unsafe-inline'" not in csp
    assert "frame-ancestors *" in csp
