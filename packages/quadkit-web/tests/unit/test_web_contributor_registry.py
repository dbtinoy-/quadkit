from __future__ import annotations

from starlette.applications import Starlette

from quadkit.contracts.web import WebContributorProtocol
from quadkit.web.contributors.registry import WebContributorRegistry


class _FakeContributor:
    @property
    def contributor_id(self) -> str:
        return "fake"

    def get_controllers(self) -> list[type]:
        return []

    def get_middleware(self) -> list[type]:
        return []

    async def mount_to_app(self, app: Starlette, container: object) -> None:  # noqa: ARG002
        return None


def test_registry_registers_and_returns_contributors_in_order() -> None:
    registry = WebContributorRegistry()
    contributor = _FakeContributor()

    assert isinstance(contributor, WebContributorProtocol)

    registry.register(contributor)

    assert registry.get("fake") is contributor
    assert registry.get_all() == [contributor]
