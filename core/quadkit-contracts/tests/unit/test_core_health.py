"""Tests for contracts health types."""

from datetime import UTC, datetime

from quadkit.contracts.core.health import (
    HealthCheckCategory,
    HealthCheckResult,
    HealthStatus,
)


class TestHealthCheckCategory:
    """Tests for HealthCheckCategory enum."""

    def test_health_check_category_values(self) -> None:
        """Test HealthCheckCategory enum values."""
        assert HealthCheckCategory.LIVENESS.value == "liveness"
        assert HealthCheckCategory.READINESS.value == "readiness"
        assert HealthCheckCategory.STARTUP.value == "startup"

    def test_health_check_category_members(self) -> None:
        """Test HealthCheckCategory has expected members."""
        members = list(HealthCheckCategory)
        assert len(members) == 3


class TestHealthStatus:
    """Tests for HealthStatus enum."""

    def test_health_status_values(self) -> None:
        """Test HealthStatus enum values."""
        assert HealthStatus.HEALTHY.value == "healthy"
        assert HealthStatus.UNHEALTHY.value == "unhealthy"
        assert HealthStatus.DEGRADED.value == "degraded"
        assert HealthStatus.UNKNOWN.value == "unknown"
        assert HealthStatus.STARTING.value == "starting"

    def test_health_status_members(self) -> None:
        """Test HealthStatus has expected members."""
        members = list(HealthStatus)
        assert len(members) == 5


class TestHealthCheckResult:
    """Tests for HealthCheckResult dataclass."""

    def test_health_check_result_default_values(self) -> None:
        """Test HealthCheckResult default values."""
        result = HealthCheckResult(component="test")

        assert result.component == "test"
        assert result.status == HealthStatus.HEALTHY
        assert result.message is None
        assert result.error is None
        assert result.duration_ms == 0.0
        assert result.details is None
        assert result.checked_at is None
        assert result.category == HealthCheckCategory.READINESS

    def test_health_check_result_with_all_fields(self) -> None:
        """Test HealthCheckResult with all fields populated."""
        checked_at = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
        result = HealthCheckResult(
            component="database",
            status=HealthStatus.UNHEALTHY,
            message="Connection failed",
            error="Connection refused",
            duration_ms=125.5,
            details={"host": "localhost", "port": 5432},
            checked_at=checked_at,
            category=HealthCheckCategory.STARTUP,
        )

        assert result.component == "database"
        assert result.status == HealthStatus.UNHEALTHY
        assert result.message == "Connection failed"
        assert result.error == "Connection refused"
        assert result.duration_ms == 125.5
        assert result.details == {"host": "localhost", "port": 5432}
        assert result.checked_at == checked_at
        assert result.category == HealthCheckCategory.STARTUP

    def test_to_dict_basic(self) -> None:
        """Test to_dict with basic fields."""
        result = HealthCheckResult(
            component="cache",
            status=HealthStatus.HEALTHY,
            duration_ms=10.5,
        )

        d = result.to_dict()

        assert d["component"] == "cache"
        assert d["category"] == HealthCheckCategory.READINESS.value
        assert d["status"] == "healthy"
        assert d["duration_ms"] == 10.5

    def test_to_dict_with_message(self) -> None:
        """Test to_dict includes message when present."""
        result = HealthCheckResult(
            component="api",
            message="All systems operational",
        )

        d = result.to_dict()

        assert d["message"] == "All systems operational"

    def test_to_dict_with_error(self) -> None:
        """Test to_dict includes error when present."""
        result = HealthCheckResult(
            component="db",
            status=HealthStatus.UNHEALTHY,
            error="Timeout",
        )

        d = result.to_dict()

        assert d["error"] == "Timeout"

    def test_to_dict_with_details(self) -> None:
        """Test to_dict includes details when present."""
        result = HealthCheckResult(
            component="queue",
            details={"pending": 5, "processed": 100},
        )

        d = result.to_dict()

        assert d["details"] == {"pending": 5, "processed": 100}

    def test_to_dict_with_checked_at(self) -> None:
        """Test to_dict formats checked_at as ISO string."""
        checked_at = datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)
        result = HealthCheckResult(
            component="service",
            checked_at=checked_at,
        )

        d = result.to_dict()

        assert d["checked_at"] == "2024-01-15T10:30:00+00:00"
        assert d["category"] == HealthCheckCategory.READINESS.value

    def test_to_dict_duration_rounded(self) -> None:
        """Test to_dict rounds duration_ms to 2 decimal places."""
        result = HealthCheckResult(
            component="test",
            duration_ms=123.456789,
        )

        d = result.to_dict()

        assert d["duration_ms"] == 123.46

    def test_to_dict_omits_none_fields(self) -> None:
        """Test to_dict omits fields that are None."""
        result = HealthCheckResult(component="minimal")

        d = result.to_dict()

        assert "message" not in d
        assert "error" not in d
        assert "details" not in d
        assert "checked_at" not in d
