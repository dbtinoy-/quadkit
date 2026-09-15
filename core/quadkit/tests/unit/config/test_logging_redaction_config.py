"""Tests for logging config classes - RedactionConfig."""

from quadkit.logging.config.redaction import RedactionConfig
from quadkit.logging.redaction import _DEFAULT_FIELD_DENYLIST


class TestRedactionConfig:
    """Tests for RedactionConfig."""

    def test_default_values(self) -> None:
        """Test RedactionConfig has correct safe-by-default values."""
        config = RedactionConfig()

        assert config.enabled is True
        assert set(config.field_denylist) == {f.lower() for f in _DEFAULT_FIELD_DENYLIST}

    def test_custom_field_denylist(self) -> None:
        """Test a custom field_denylist overrides the default."""
        config = RedactionConfig(field_denylist=("custom_field", "other"))

        assert config.enabled is True
        assert config.field_denylist == ("custom_field", "other")

    def test_disabled(self) -> None:
        """Test RedactionConfig with enabled=False."""
        config = RedactionConfig(enabled=False)

        assert config.enabled is False
        assert set(config.field_denylist) == {f.lower() for f in _DEFAULT_FIELD_DENYLIST}

    def test_construction_from_dict(self) -> None:
        """Test RedactionConfig constructs from a dict via model_validate."""
        config = RedactionConfig.model_validate(
            {"enabled": False, "field_denylist": ("a",)}
        )

        assert config.enabled is False
        assert config.field_denylist == ("a",)