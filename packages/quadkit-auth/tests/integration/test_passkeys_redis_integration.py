import os
from typing import Any

import pytest

from quadkit.contracts.infra.cache.exceptions import CacheError, CacheWriteError
from quadkit.result import Err, Ok, Result


@pytest.mark.integration
@pytest.mark.asyncio
async def test_passkey_flow_with_redis_backend():
    """Integration test: run passkey register/auth flows using a real redis backend.

    Requires:
      - `redis.asyncio` installed
      - A reachable Redis server available via REDIS_URL env var (defaults to redis://localhost:16379/0)

    If requirements aren't met the test will be skipped.
    """
    try:
        import redis.asyncio as aioredis
        import redis.exceptions as redis_exc
    except ImportError:  # pragma: no cover - skip if redis lib not available
        pytest.skip("redis.asyncio not available; skipping integration test")

    redis_url = os.environ.get("REDIS_URL", "redis://localhost:16379/0")

    try:
        client = await aioredis.from_url(redis_url)
        # Basic ping to verify connectivity
        await client.ping()
    except (ConnectionError, TimeoutError, OSError, Exception) as e:
        # Also catch redis-specific exceptions
        if "redis" in type(e).__module__.lower() or isinstance(
            e, getattr(redis_exc, "ConnectionError", ConnectionError)
        ):
            pytest.skip(
                f"Could not connect to Redis at {redis_url}; "
                "set REDIS_URL to run this integration test",
            )
        raise

    # Minimal user/store/provider stubs
    class _FakeUser:
        def __init__(self, user_id, username):
            self.user_id = user_id
            self.username = username
            self.profile = {}

    class _FakeStore:
        def __init__(self):
            self._users = {}

        async def get_user_by_id(self, user_id):
            return self._users.get(user_id)

        async def update_user(self, user):
            self._users[user.user_id] = user

    class _FakeProvider:
        def __init__(self, store, cache_client):
            self.user_store = store
            self.cache_service = cache_client

        async def get_user(self, user_id):
            return await self.user_store.get_user_by_id(user_id)

    store = _FakeStore()
    user = _FakeUser("u-redis", "redis-user")
    store._users[user.user_id] = user

    # Adapt the Redis client to CacheBackendProtocol for the real-backend test.
    class RedisWrapper:
        def __init__(self, r_client: Any) -> None:
            self._r = r_client

        async def set(
            self, key: str, value: Any, ttl: int | None = None
        ) -> Result[None, CacheError]:
            try:
                await self._r.set(key, value, ex=ttl)
            except Exception as exc:  # noqa: BLE001 - protocol adapter translates backend errors
                return Err(CacheWriteError(key, str(exc)))
            return Ok(None)

        async def get(self, key: str) -> Result[Any | None, CacheError]:
            try:
                return Ok(await self._r.get(key))
            except Exception as exc:  # noqa: BLE001 - protocol adapter translates backend errors
                return Err(CacheError(f"Cache read failed for key {key}: {exc}"))

        async def delete(self, key: str) -> Result[bool, CacheError]:
            try:
                deleted = await self._r.delete(key)
            except Exception as exc:  # noqa: BLE001 - protocol adapter translates backend errors
                return Err(CacheError(f"Cache delete failed for key {key}: {exc}"))
            return Ok(bool(deleted))

    wrapper = RedisWrapper(client)

    # Import service lazily to ensure we use project code
    from quadkit.auth.authn.passkeys import PasskeyService

    service = PasskeyService(store, wrapper)

    # Run registration/auth flow
    reg_id, _challenge = await service.start_registration(
        user.user_id,
        name="Redis Device",
    )

    # Client creates keypair and registers
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    priv = ec.generate_private_key(ec.SECP256R1())
    pub = priv.public_key()
    pub_pem = pub.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    credential_id = "redis-cred-1"

    ok = await service.finish_registration(reg_id, credential_id, pub_pem)
    assert ok

    # Start auth and finish
    auth_id, auth_challenge, cred_ids = await service.start_authentication(user.user_id)
    assert credential_id in cred_ids

    signature = priv.sign(auth_challenge.encode("utf-8"), ec.ECDSA(hashes.SHA256()))
    verified = await service.finish_authentication(auth_id, credential_id, signature)
    assert verified

    # cleanup
    await client.aclose()
