"""Tests for component exceptions from contracts."""

from quadkit.contracts.exceptions.components import (
    ComponentConnectionError,
    ComponentError,
    DriverNotAvailableError,
    KeyExistsError,
    KeyNotFoundError,
    LockAcquisitionError,
    LockNotHeldError,
    PubSubError,
    SecretNotFoundError,
)
from quadkit.contracts.exceptions.security import SecretAccessError


class TestComponentExceptionHierarchy:
    """Tests for component exception inheritance."""

    def test_component_error_inherits_from_quadkit(self) -> None:
        """ComponentError inherits from QuadkitError."""
        assert issubclass(ComponentError, Exception)

    def test_component_connection_error_inherits(self) -> None:
        """ComponentConnectionError inherits from InfrastructureError."""
        assert issubclass(ComponentConnectionError, Exception)

    def test_key_not_found_inherits(self) -> None:
        """KeyNotFoundError inherits from NotFoundError."""
        assert issubclass(KeyNotFoundError, Exception)

    def test_key_exists_inherits(self) -> None:
        """KeyExistsError inherits from ConflictError."""
        assert issubclass(KeyExistsError, Exception)

    def test_pubsub_error_inherits(self) -> None:
        """PubSubError inherits from InfrastructureError."""
        assert issubclass(PubSubError, Exception)

    def test_secret_not_found_inherits(self) -> None:
        """SecretNotFoundError inherits from NotFoundError."""
        assert issubclass(SecretNotFoundError, Exception)

    def test_lock_acquisition_error_inherits(self) -> None:
        """LockAcquisitionError inherits from LockError."""
        assert issubclass(LockAcquisitionError, Exception)

    def test_lock_not_held_error_inherits(self) -> None:
        """LockNotHeldError inherits from LockError."""
        assert issubclass(LockNotHeldError, Exception)


class TestComponentErrorCodes:
    """Tests for component exception error codes."""

    def test_component_error_has_code(self) -> None:
        """ComponentError has _code."""
        exc = ComponentError(message="Error")
        assert exc._code == "QK_ERR_INFRA_004"

    def test_component_connection_error_has_code(self) -> None:
        """ComponentConnectionError has _code."""
        exc = ComponentConnectionError(message="Connection failed")
        assert exc._code == "QK_ERR_INFRA_005"

    def test_key_not_found_error_has_code(self) -> None:
        """KeyNotFoundError has _code."""
        exc = KeyNotFoundError(key="test")
        assert exc._code == "QK_ERR_INFRA_006"

    def test_key_exists_error_has_code(self) -> None:
        """KeyExistsError has _code."""
        exc = KeyExistsError(key="test")
        assert exc._code == "QK_ERR_INFRA_007"

    def test_pubsub_error_has_code(self) -> None:
        """PubSubError has _code."""
        exc = PubSubError(message="PubSub error")
        assert exc._code == "QK_ERR_INFRA_008"

    def test_secret_not_found_error_has_code(self) -> None:
        """SecretNotFoundError has _code."""
        exc = SecretNotFoundError(secret_name="api_key")
        assert exc._code == "QK_ERR_INFRA_009"

    def test_secret_access_error_has_code(self) -> None:
        """SecretAccessError has _code."""
        exc = SecretAccessError(secret_name="api_key")
        assert exc._code == "QK_ERR_SEC_005"

    def test_driver_not_available_error_has_code(self) -> None:
        """DriverNotAvailableError has _code."""
        exc = DriverNotAvailableError(driver_type="mysql")
        assert exc._code == "QK_ERR_INFRA_010"


class TestComponentErrorAttributes:
    """Tests for component exception attributes."""

    def test_component_error_stores_types(self) -> None:
        """ComponentError stores component_type and driver_type."""
        exc = ComponentError(
            message="Error",
            component_type="cache",
            driver_type="redis",
        )
        assert exc.component_type == "cache"
        assert exc.driver_type == "redis"

    def test_key_not_found_stores_key(self) -> None:
        """KeyNotFoundError stores key."""
        exc = KeyNotFoundError(key="user:123")
        assert exc.key == "user:123"

    def test_key_exists_stores_key(self) -> None:
        """KeyExistsError stores key."""
        exc = KeyExistsError(key="user:123")
        assert exc.key == "user:123"

    def test_pubsub_error_stores_topic(self) -> None:
        """PubSubError stores topic."""
        exc = PubSubError(message="Error", topic="notifications")
        assert exc.topic == "notifications"

    def test_secret_not_found_stores_name(self) -> None:
        """SecretNotFoundError stores secret_name."""
        exc = SecretNotFoundError(secret_name="db_password")
        assert exc.secret_name == "db_password"

    def test_secret_access_error_stores_in_details(self) -> None:
        """SecretAccessError stores secret_name and operation in details."""
        exc = SecretAccessError(secret_name="api_key", operation="write")
        assert exc.details["secret_name"] == "api_key"
        assert exc.details["operation"] == "write"

    def test_lock_acquisition_error_stores_resource(self) -> None:
        """LockAcquisitionError stores resource."""
        exc = LockAcquisitionError(resource="order:123")
        assert exc.resource == "order:123"

    def test_lock_not_held_error_stores_resource(self) -> None:
        """LockNotHeldError stores resource."""
        exc = LockNotHeldError(resource="order:123")
        assert exc.resource == "order:123"

    def test_driver_not_available_stores_type_and_hint(self) -> None:
        """DriverNotAvailableError stores driver_type and install_hint."""
        exc = DriverNotAvailableError(
            driver_type="postgres", install_hint="pip install asyncpg"
        )
        assert exc.driver_type == "postgres"
        assert exc.install_hint == "pip install asyncpg"
