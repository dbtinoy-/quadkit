import os

import pytest


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
        if "redis" in type(e).__module__.lower() or isinstance(e, getattr(redis_exc, 'ConnectionError', ConnectionError)):
            pytest.skip(
                "Could not connect to Redis at %s; set REDIS_URL to run this integration test"
                % redis_url,
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

    # Wrap redis client into the minimal async cache interface expected by _PendingStore
    class RedisWrapper:
        def __init__(self, r_client):
            self._r = r_client

        async def set(self, k, v, ex=None):
            await self._r.set(k, v, ex=ex)

        async def get(self, k):
            return await self._r.get(k)

        async def delete(self, k):
            await self._r.delete(k)

    wrapper = RedisWrapper(client)
    
    # Import service lazily to ensure we use project code
    from quadkit.auth.authn.passkeys import PasskeyService

    service = PasskeyService(store, wrapper)

    # Run registration/auth flow
    reg_id, challenge = await service.start_registration(
        user.user_id, name="Redis Device",
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
