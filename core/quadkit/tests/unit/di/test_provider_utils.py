import pytest

from quadkit.di.provider_utils import resolve_credential, resolve_optional


class _ContainerWithOptional:
    def __init__(self, value: object) -> None:
        self._value = value

    async def resolve_optional(self, protocol: type) -> object:
        return self._value


class _ContainerResolveOnly:
    def __init__(self, bindings: dict[type, object]) -> None:
        self.bindings = bindings

    async def resolve(self, key: type) -> object:
        if key not in self.bindings:
            raise LookupError(key)
        return self.bindings[key]


class _NeverResolvingContainer:
    async def resolve(self, key: type) -> object:
        raise LookupError(key)


class _SecretStore:
    def __init__(self, values: dict[str, str]) -> None:
        self.values = values

    async def get(self, name: str) -> str | None:
        return self.values.get(name)


@pytest.mark.asyncio
async def test_resolve_optional_uses_resolve_optional_method() -> None:
    container = _ContainerWithOptional(42)

    result = await resolve_optional(container, int)

    assert result == 42


@pytest.mark.asyncio
async def test_resolve_optional_falls_back_to_resolve() -> None:
    container = _ContainerResolveOnly({str: "value"})

    result = await resolve_optional(container, str)

    assert result == "value"


@pytest.mark.asyncio
async def test_resolve_optional_returns_none_when_unavailable() -> None:
    container = _NeverResolvingContainer()

    result = await resolve_optional(container, int)

    assert result is None


@pytest.mark.asyncio
async def test_resolve_credential_prefers_secret_store(monkeypatch) -> None:
    store = _SecretStore({"qk_key": "stored-value"})
    monkeypatch.setenv("QK_KEY", "env-value")

    result = await resolve_credential(store, "qk_key")

    assert result == "stored-value"


@pytest.mark.asyncio
async def test_resolve_credential_falls_back_to_env_var(monkeypatch) -> None:
    monkeypatch.setenv("QK_MISSING_FALLBACK", "env-value")

    result = await resolve_credential(None, "qk_missing_fallback")

    assert result == "env-value"