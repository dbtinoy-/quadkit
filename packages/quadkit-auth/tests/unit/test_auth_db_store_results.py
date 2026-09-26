from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.auth.storage.db_stores import SQLUserStore




@pytest.mark.asyncio
async def test_list_users_handles_dict_result():
    # Mock DB provider returning a single dict for list
    mock_db = MagicMock()

    row = {
        "user_id": "u2",
        "username": "user2",
        "email": "u2@example.com",
        "hashed_password": "h",
    }
    # Provider-level execute_query returns a dict for the list
    mock_db.execute_query = AsyncMock(return_value=row)

    store = SQLUserStore(mock_db)

    users = await store.list_users()
    assert isinstance(users, list)
    assert users[0].name == "user2"


@pytest.mark.asyncio
async def test_count_users_handles_list_result():
    # Mock DB provider returning a list for count
    mock_db = MagicMock()

    mock_db.execute_query = AsyncMock(return_value=[{"count": 5}])

    store = SQLUserStore(mock_db)

    c = await store.count_users()
    assert c == 5
