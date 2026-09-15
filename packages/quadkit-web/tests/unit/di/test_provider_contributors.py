from __future__ import annotations

import pytest

from quadkit.web.di.provider import WebProvider


class _ExplicitController:
    @classmethod
    def collect_routes(cls) -> list[dict[str, str]]:
        return []


class _ContributedController:
    @classmethod
    def collect_routes(cls) -> list[dict[str, str]]:
        return []


class _ContributedMiddleware:
    pass


class _FakeContributor:
    @property
    def contributor_id(self) -> str:
        return "graphql"

    def get_controllers(self) -> list[type]:
        return [_ExplicitController, _ContributedController]

    def get_middleware(self) -> list[type]:
        return [_ContributedMiddleware]

    async def mount_to_app(self, app, container) -> None:  # noqa: ANN001, ARG002
        return None


class _FakeRegistrar:
    def __init__(self) -> None:
        self.singleton_tokens: list[object] = []

    def singleton(self, token: object, factory: object) -> None:  # noqa: ARG002
        self.singleton_tokens.append(token)

    def transient(self, token: object, factory: object) -> None:  # noqa: ARG002
        return None

    def scoped(self, token: object, factory: object) -> None:  # noqa: ARG002
        return None

    def has(self, token: object) -> bool:  # noqa: ARG002
        return False


@pytest.mark.asyncio
async def test_register_merges_discovered_controllers_and_middleware_without_duplicates(
    monkeypatch,
) -> None:
    provider = WebProvider(controllers=[_ExplicitController])
    registrar = _FakeRegistrar()

    monkeypatch.setattr(
        "quadkit.web.contributors.discovery.load_web_contributors",
        lambda: [_FakeContributor()],
    )

    await provider.register(registrar)

    assert provider.controllers == [_ExplicitController, _ContributedController]
    assert provider.middleware == [_ContributedMiddleware]
    assert _ExplicitController in registrar.singleton_tokens
    assert _ContributedController in registrar.singleton_tokens
