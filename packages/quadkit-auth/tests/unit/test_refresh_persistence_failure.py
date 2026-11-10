"""Failed revocation must never issue replacement credentials."""

from unittest.mock import AsyncMock, Mock

from pydantic import SecretStr
import pytest

from quadkit.auth.authn.jwt import JWTTokenManager
from quadkit.auth.exceptions import TokenError
from quadkit.auth.models.user import User
from quadkit.contracts.auth.exceptions import TokenError as ContractTokenError
from quadkit.result import Err


@pytest.mark.asyncio
async def test_refresh_refuses_failed_legacy_revocation():
    manager = JWTTokenManager(
        current_key_id="test",
        keys={"test": SecretStr("test-refresh-persistence-key-at-least-32-bytes")},
    )
    token = manager.create_refresh_token(
        User(user_id="user", email="user@example.test")
    )
    manager.logout = AsyncMock(return_value=Err(ContractTokenError("write failed")))
    manager.create_token_pair = Mock(side_effect=AssertionError("must not mint"))
    with pytest.raises(TokenError, match="revocation failed"):
        await manager.refresh_access_token(token)
    manager.create_token_pair.assert_not_called()
