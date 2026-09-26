import pytest

from quadkit.auth.authn.security import PasswordHasher, PasswordPolicy
from quadkit.auth.authn.user_service import UserService
from quadkit.auth.exceptions import PasswordPolicyError
from quadkit.auth.storage.token_store import InMemoryUserStore


@pytest.mark.asyncio
async def test_change_password_adds_history():
    user_store = InMemoryUserStore()
    policy = PasswordPolicy(prevent_reuse=True, history_size=2)
    service = UserService(password_policy=policy, user_store=user_store)

    result = await service.create_user("alice", "alice@example.com", "Secure!Pass42")
    assert result.is_ok()
    user = result.unwrap()

    change_result = await service.change_user_password(user.user_id, "Secure!Pass42", "Different#Pass55")
    assert change_result.is_ok()
    updated = await service.get_user(user.user_id)
    creds = await service.user_store.get_credentials(user.user_id)
    assert updated is not None
    assert creds is not None
    assert len(creds.previous_hashes) == 1
    assert await PasswordHasher().verify("Secure!Pass42", creds.previous_hashes[0])

    change_result2 = await service.change_user_password(user.user_id, "Different#Pass55", "Another@Pass77")
    assert change_result2.is_ok()
    updated = await service.get_user(user.user_id)
    creds = await service.user_store.get_credentials(user.user_id)
    assert updated is not None
    assert creds is not None
    assert len(creds.previous_hashes) == 2
    assert await PasswordHasher().verify("Different#Pass55", creds.previous_hashes[0])


@pytest.mark.asyncio
async def test_prevent_password_reuse():
    user_store = InMemoryUserStore()
    policy = PasswordPolicy(prevent_reuse=True, history_size=5)
    service = UserService(password_policy=policy, user_store=user_store)

    result = await service.create_user("bob", "bob@example.com", "OrigPass")
    assert result.is_ok()
    user = result.unwrap()

    change_result = await service.change_user_password(user.user_id, "OrigPass", "OrigPass")
    assert change_result.is_err()
    assert isinstance(change_result.unwrap_err(), PasswordPolicyError)


@pytest.mark.asyncio
async def test_admin_set_password_bypasses_reuse_check():
    user_store = InMemoryUserStore()
    policy = PasswordPolicy(prevent_reuse=True, history_size=2)
    service = UserService(password_policy=policy, user_store=user_store)

    result = await service.create_user("admin_user", "admin@example.com", "AdminSecure!42")
    assert result.is_ok()
    user = result.unwrap()

    await service.set_user_password(user.user_id, "AdminSecure!42", force=True)
    creds = await service.user_store.get_credentials(user.user_id)
    assert creds is not None
    assert await PasswordHasher().verify("AdminSecure!42", creds.hashed_password)
