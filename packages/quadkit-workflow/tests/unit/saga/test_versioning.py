from __future__ import annotations

import pytest

from quadkit.contracts.workflow.protocols import SagaState
from quadkit.contracts.workflow import SagaVersionMismatchError
from quadkit.workflow.saga.base import AbstractSaga


class V1OrderSaga(AbstractSaga):
    VERSION = 1

    def get_id(self) -> str:
        return "v1-order"

    def is_completed(self) -> bool:
        return self.state == SagaState.COMPLETED


class V2OrderSaga(AbstractSaga):
    VERSION = 2

    def get_id(self) -> str:
        return "v2-order"

    def is_completed(self) -> bool:
        return self.state == SagaState.COMPLETED


class TestSagaVersioning:
    def test_default_version_is_one(self) -> None:
        saga = V1OrderSaga()
        assert saga.get_version() == 1

    def test_version_class_var_respected(self) -> None:
        saga = V2OrderSaga()
        assert saga.get_version() == 2

    def test_compatible_version_accepted(self) -> None:
        saga = V1OrderSaga()
        assert saga.is_compatible_with(1) is True

    def test_incompatible_version_rejected(self) -> None:
        saga = V2OrderSaga()
        assert saga.is_compatible_with(1) is False

    @pytest.mark.asyncio
    async def test_load_state_raises_on_version_mismatch(self) -> None:
        from unittest.mock import AsyncMock, MagicMock

        mock_store = MagicMock()
        mock_store.load = AsyncMock(return_value=MagicMock(state="running", version=1))
        saga = V2OrderSaga()
        saga._store = mock_store
        result = await saga._load_state()
        assert result.is_err()
        err = result.unwrap_err()
        assert isinstance(err, SagaVersionMismatchError)
        assert err.stored_version == 1
        assert err.expected_version == 2

    @pytest.mark.asyncio
    async def test_persist_state_includes_version(self) -> None:
        from unittest.mock import AsyncMock, MagicMock

        mock_store = MagicMock()
        mock_store.save = AsyncMock()
        saga = V1OrderSaga()
        saga._store = mock_store
        await saga._persist_state()
        call_args = mock_store.save.call_args
        metadata = call_args[0][2] if len(call_args[0]) > 2 else call_args[1].get("metadata", {})
        assert metadata.get("version") == 1
