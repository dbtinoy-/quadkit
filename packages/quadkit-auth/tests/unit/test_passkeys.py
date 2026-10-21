import hashlib

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
import pytest

from quadkit import serialization as json
from quadkit.auth.authn.passkeys import PasskeyService


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
    def __init__(self, store):
        self.user_store = store

    async def get_user(self, user_id):
        return await self.user_store.get_user_by_id(user_id)


# ---------------------------------------------------------------------------
# Helpers shared across tests
# ---------------------------------------------------------------------------


def _make_keypair():
    priv = ec.generate_private_key(ec.SECP256R1())
    pub = priv.public_key()
    pub_pem = pub.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    return priv, pub_pem


async def _register_passkey(service, user_id, credential_id, *, origin=None):
    reg_id, _challenge = await service.start_registration(user_id, name="test key")
    priv, pub_pem = _make_keypair()
    ok = await service.finish_registration(
        reg_id, credential_id, pub_pem, origin=origin
    )
    assert ok, "Registration unexpectedly failed in helper"
    return priv


async def _sign_challenge(priv, challenge: str) -> bytes:
    return priv.sign(challenge.encode("utf-8"), ec.ECDSA(hashes.SHA256()))


# ---------------------------------------------------------------------------
# Existing end-to-end flow (no origin / no sign-counter)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_passkey_register_and_auth_flow():
    store = _FakeStore()
    user = _FakeUser("u1", "alice")
    store._users[user.user_id] = user

    # Simulate a cache-backed provider with the standard Result contract.
    from quadkit.result import Ok

    class DummyCache:
        def __init__(self):
            self._store = {}

        async def set(self, key, value, ttl=None):
            self._store[key] = value
            return Ok(None)

        async def get(self, key):
            return Ok(self._store.get(key))

        async def delete(self, key):
            return Ok(self._store.pop(key, None) is not None)

    cache_service = DummyCache()
    service = PasskeyService(store, cache_service)

    # Start registration
    reg_id, _challenge = await service.start_registration(
        user.user_id,
        name="Alice Phone",
    )

    # Client generates a key and provides credential + public key
    priv = ec.generate_private_key(ec.SECP256R1())
    pub = priv.public_key()
    pub_pem = pub.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    credential_id = "cred-1"

    ok = await service.finish_registration(reg_id, credential_id, pub_pem)
    assert ok

    # Start auth
    auth_id, auth_challenge, credential_ids = await service.start_authentication(
        user.user_id,
    )
    assert credential_id in credential_ids

    # Client signs the challenge using ECDSA SHA256
    signature_der = priv.sign(auth_challenge.encode("utf-8"), ec.ECDSA(hashes.SHA256()))
    verified = await service.finish_authentication(
        auth_id,
        credential_id,
        signature_der,
    )
    assert verified


# ---------------------------------------------------------------------------
# Origin validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_finish_registration_rejects_wrong_origin():
    store = _FakeStore()
    user = _FakeUser("u2", "bob")
    store._users[user.user_id] = user

    service = PasskeyService(store, allowed_origins={"https://example.com"})

    reg_id, _ch = await service.start_registration(user.user_id)
    _priv, pub_pem = _make_keypair()

    # Wrong origin must be rejected.
    result = await service.finish_registration(
        reg_id, "cred-2", pub_pem, origin="https://evil.com"
    )
    assert result is False


@pytest.mark.asyncio
async def test_finish_registration_accepts_correct_origin():
    store = _FakeStore()
    user = _FakeUser("u3", "carol")
    store._users[user.user_id] = user

    service = PasskeyService(store, allowed_origins={"https://example.com"})

    reg_id, _ch = await service.start_registration(user.user_id)
    _priv, pub_pem = _make_keypair()

    result = await service.finish_registration(
        reg_id, "cred-3", pub_pem, origin="https://example.com"
    )
    assert result is True


@pytest.mark.asyncio
async def test_finish_registration_rejects_missing_origin_when_required():
    store = _FakeStore()
    user = _FakeUser("u4", "dave")
    store._users[user.user_id] = user

    service = PasskeyService(store, allowed_origins={"https://example.com"})

    reg_id, _ch = await service.start_registration(user.user_id)
    _priv, pub_pem = _make_keypair()

    result = await service.finish_registration(reg_id, "cred-4", pub_pem)
    assert result is False


@pytest.mark.asyncio
async def test_finish_authentication_rejects_wrong_origin():
    store = _FakeStore()
    user = _FakeUser("u5", "eve")
    store._users[user.user_id] = user

    service = PasskeyService(store, allowed_origins={"https://example.com"})

    priv = await _register_passkey(
        service, user.user_id, "cred-5", origin="https://example.com"
    )

    auth_id, ch, _ = await service.start_authentication(user.user_id)
    sig = await _sign_challenge(priv, ch)

    result = await service.finish_authentication(
        auth_id, "cred-5", sig, origin="https://evil.com"
    )
    assert result is False


@pytest.mark.asyncio
async def test_finish_authentication_accepts_correct_origin():
    store = _FakeStore()
    user = _FakeUser("u6", "frank")
    store._users[user.user_id] = user

    service = PasskeyService(store, allowed_origins={"https://example.com"})

    priv = await _register_passkey(
        service, user.user_id, "cred-6", origin="https://example.com"
    )

    auth_id, ch, _ = await service.start_authentication(user.user_id)
    sig = await _sign_challenge(priv, ch)

    result = await service.finish_authentication(
        auth_id, "cred-6", sig, origin="https://example.com"
    )
    assert result is True


# ---------------------------------------------------------------------------
# Sign counter monotonicity (cloned-authenticator detection)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sign_counter_advances_on_success():
    store = _FakeStore()
    user = _FakeUser("u7", "grace")
    store._users[user.user_id] = user

    service = PasskeyService(store)
    priv = await _register_passkey(service, user.user_id, "cred-7")

    auth_id, ch, _ = await service.start_authentication(user.user_id)
    sig = await _sign_challenge(priv, ch)

    result = await service.finish_authentication(
        auth_id, "cred-7", sig, new_sign_count=1
    )
    assert result is True

    # Stored count should now be 1.
    stored = store._users[user.user_id]
    pk = next(p for p in stored.profile["passkeys"] if p["credential_id"] == "cred-7")
    assert pk["sign_count"] == 1


@pytest.mark.asyncio
async def test_sign_counter_equal_is_rejected():
    store = _FakeStore()
    user = _FakeUser("u8", "heidi")
    store._users[user.user_id] = user

    service = PasskeyService(store)
    priv = await _register_passkey(service, user.user_id, "cred-8")

    # First auth — advance counter to 2.
    auth_id, ch, _ = await service.start_authentication(user.user_id)
    sig = await _sign_challenge(priv, ch)
    assert await service.finish_authentication(auth_id, "cred-8", sig, new_sign_count=2)

    # Second auth — replay same counter value (cloned authenticator).
    auth_id2, ch2, _ = await service.start_authentication(user.user_id)
    sig2 = await _sign_challenge(priv, ch2)
    result = await service.finish_authentication(
        auth_id2, "cred-8", sig2, new_sign_count=2
    )
    assert result is False


@pytest.mark.asyncio
async def test_sign_counter_regression_is_rejected():
    store = _FakeStore()
    user = _FakeUser("u9", "ivan")
    store._users[user.user_id] = user

    service = PasskeyService(store)
    priv = await _register_passkey(service, user.user_id, "cred-9")

    # Advance counter to 5.
    auth_id, ch, _ = await service.start_authentication(user.user_id)
    sig = await _sign_challenge(priv, ch)
    assert await service.finish_authentication(auth_id, "cred-9", sig, new_sign_count=5)

    # Try to authenticate with counter 3 (regression).
    auth_id2, ch2, _ = await service.start_authentication(user.user_id)
    sig2 = await _sign_challenge(priv, ch2)
    result = await service.finish_authentication(
        auth_id2, "cred-9", sig2, new_sign_count=3
    )
    assert result is False


@pytest.mark.asyncio
async def test_sign_counter_omitted_is_allowed():
    """When no sign_count is provided the check is skipped (backward compat)."""
    store = _FakeStore()
    user = _FakeUser("u10", "judy")
    store._users[user.user_id] = user

    service = PasskeyService(store)
    priv = await _register_passkey(service, user.user_id, "cred-10")

    auth_id, ch, _ = await service.start_authentication(user.user_id)
    sig = await _sign_challenge(priv, ch)

    # No new_sign_count — should succeed.
    result = await service.finish_authentication(auth_id, "cred-10", sig)
    assert result is True


@pytest.mark.asyncio
async def test_browser_webauthn_assertion_validates_client_data_rp_and_signature():
    """Browser ArrayBuffers are verified without trusting client sign_count."""
    store = _FakeStore()
    user = _FakeUser("u11", "kate")
    store._users[user.user_id] = user

    service = PasskeyService(
        store,
        rp_id="example.com",
        allowed_origins={"https://example.com"},
    )
    priv = await _register_passkey(
        service,
        user.user_id,
        "cred-11",
        origin="https://example.com",
    )
    auth_id, challenge, _ = await service.start_authentication(user.user_id)

    client_data_json = json.dumps(
        {
            "type": "webauthn.get",
            "challenge": challenge.rstrip("="),
            "origin": "https://example.com",
        },
        separators=(",", ":"),
    )
    authenticator_data = (
        hashlib.sha256(b"example.com").digest() + b"\x01" + (1).to_bytes(4, "big")
    )
    signed = authenticator_data + hashlib.sha256(client_data_json).digest()
    signature = priv.sign(signed, ec.ECDSA(hashes.SHA256()))

    assert await service.finish_authentication(
        auth_id,
        "cred-11",
        signature,
        origin="https://example.com",
        authenticator_data=authenticator_data,
        client_data_json=client_data_json,
    )
    stored = store._users[user.user_id]
    pk = next(p for p in stored.profile["passkeys"] if p["credential_id"] == "cred-11")
    assert pk["sign_count"] == 1
