"""Tests for admin contract errors."""
from __future__ import annotations

import pytest

from quadkit.contracts.admin.errors import (
    AdminError,
    HealthCheckNotFoundError,
    WidgetNotFoundError,
)
from quadkit.contracts.exceptions.base import QuadkitError


class TestAdminError:
    def test_inherits_quadkit_error(self) -> None:
        assert issubclass(AdminError, QuadkitError)

    def test_instantiation(self) -> None:
        err = AdminError("test error")
        assert "test error" in str(err)

    def test_catchable_as_quadkit_error(self) -> None:
        try:
            raise AdminError("boom")
        except QuadkitError as e:
            assert isinstance(e, AdminError)


class TestWidgetNotFoundError:
    """Test WidgetNotFoundError frozen dataclass."""

    def test_instantiation(self) -> None:
        """Test creating a WidgetNotFoundError instance."""
        error = WidgetNotFoundError("cache", "hit-ratio")
        assert error.contributor_name == "cache"
        assert error.widget_name == "hit-ratio"

    def test_frozen_immutable(self) -> None:
        """Test that WidgetNotFoundError is frozen (immutable)."""
        error = WidgetNotFoundError("web", "server-status")
        with pytest.raises(Exception):  # FrozenInstanceError
            error.contributor_name = "changed"  # type: ignore[misc]

    def test_hashable(self) -> None:
        """Test that WidgetNotFoundError is hashable (required for frozen dataclass)."""
        error1 = WidgetNotFoundError("cache", "hit-ratio")
        error2 = WidgetNotFoundError("cache", "hit-ratio")
        error3 = WidgetNotFoundError("web", "status")

        # Should be hashable
        hash_val = hash(error1)
        assert isinstance(hash_val, int)

        # Equal instances should have equal hashes
        assert hash(error1) == hash(error2)

        # Can be used in sets
        error_set = {error1, error2, error3}
        assert len(error_set) == 2  # error1 and error2 are equal

    def test_equality(self) -> None:
        """Test that WidgetNotFoundError instances compare by value."""
        error1 = WidgetNotFoundError("cache", "hit-ratio")
        error2 = WidgetNotFoundError("cache", "hit-ratio")
        error3 = WidgetNotFoundError("web", "status")

        assert error1 == error2
        assert error1 != error3

    def test_slots_no_dict(self) -> None:
        """Test that WidgetNotFoundError uses slots (no __dict__)."""
        error = WidgetNotFoundError("cache", "hit-ratio")
        assert not hasattr(error, "__dict__")

    def test_str_representation(self) -> None:
        """Test string representation."""
        error = WidgetNotFoundError("cache", "hit-ratio")
        error_str = str(error)
        assert "cache" in error_str
        assert "hit-ratio" in error_str


class TestHealthCheckNotFoundError:
    """Test HealthCheckNotFoundError frozen dataclass."""

    def test_instantiation(self) -> None:
        """Test creating a HealthCheckNotFoundError instance."""
        error = HealthCheckNotFoundError("sql", "connection-pool")
        assert error.contributor_name == "sql"
        assert error.check_name == "connection-pool"

    def test_frozen_immutable(self) -> None:
        """Test that HealthCheckNotFoundError is frozen (immutable)."""
        error = HealthCheckNotFoundError("cache", "backend-ping")
        with pytest.raises(Exception):  # FrozenInstanceError
            error.contributor_name = "changed"  # type: ignore[misc]

    def test_hashable(self) -> None:
        """Test that HealthCheckNotFoundError is hashable."""
        error1 = HealthCheckNotFoundError("sql", "connection-pool")
        error2 = HealthCheckNotFoundError("sql", "connection-pool")
        error3 = HealthCheckNotFoundError("cache", "backend-ping")

        # Should be hashable
        hash_val = hash(error1)
        assert isinstance(hash_val, int)

        # Equal instances should have equal hashes
        assert hash(error1) == hash(error2)

        # Can be used in sets
        error_set = {error1, error2, error3}
        assert len(error_set) == 2

    def test_equality(self) -> None:
        """Test that HealthCheckNotFoundError instances compare by value."""
        error1 = HealthCheckNotFoundError("sql", "connection-pool")
        error2 = HealthCheckNotFoundError("sql", "connection-pool")
        error3 = HealthCheckNotFoundError("cache", "backend-ping")

        assert error1 == error2
        assert error1 != error3

    def test_slots_no_dict(self) -> None:
        """Test that HealthCheckNotFoundError uses slots."""
        error = HealthCheckNotFoundError("sql", "connection-pool")
        assert not hasattr(error, "__dict__")

    def test_str_representation(self) -> None:
        """Test string representation."""
        error = HealthCheckNotFoundError("sql", "connection-pool")
        error_str = str(error)
        assert "sql" in error_str
        assert "connection-pool" in error_str
