import pytest

from quadkit.contracts.exceptions.container import ContainerValidationError
from quadkit.di.container import Container
from quadkit.contracts.exceptions import ContainerError


@pytest.mark.asyncio
async def test_container_freeze_blocks_registration():
    container = Container()
    # initial registration should succeed
    container.transient(str, lambda: "foo")
    # freezing
    container.freeze()

    # resolution of existing service still works
    result = await container.resolve(str)
    assert result == "foo"

    # subsequent registrations are forbidden
    with pytest.raises(ContainerError):
        container.transient(int, lambda: 1)
    with pytest.raises(ContainerError):
        container.singleton(bool, True)
    with pytest.raises(ContainerError):
        container.scoped(float, lambda: 3.14)
    with pytest.raises(ContainerError):
        container.clear()


@pytest.mark.asyncio
async def test_freeze_validate_true_raises_on_invalid_container():
    """freeze() with validate=True raises ContainerValidationError when issues exist."""
    from unittest.mock import patch

    container = Container()
    container.transient(str, lambda: "hello")

    with patch.object(
        container,
        "validate",
        return_value=["Scope violation: Singleton 'A' depends on scoped 'B'"],
    ):
        with pytest.raises(ContainerValidationError) as exc_info:
            container.freeze()

    assert "Scope violation" in str(exc_info.value)
    assert exc_info.value.issues == ["Scope violation: Singleton 'A' depends on scoped 'B'"]


@pytest.mark.asyncio
async def test_freeze_validate_false_skips_validation():
    """freeze(validate=False) freezes without running validation."""
    from unittest.mock import patch

    container = Container()
    container.transient(str, lambda: "hello")

    # Even if validate() would return issues, freeze(validate=False) should not raise
    with patch.object(
        container,
        "validate",
        return_value=["some issue"],
    ) as mock_validate:
        container.freeze(validate=False)  # Must not raise

    mock_validate.assert_not_called()
    assert container.is_frozen
