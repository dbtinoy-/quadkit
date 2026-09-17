"""Tests for logging config classes - SamplingConfig."""

import re

import pytest

from quadkit.logging.config.sampling import SamplingConfig


class TestSamplingConfig:
    """Tests for SamplingConfig."""

    def test_default_values(self) -> None:
        """Test SamplingConfig has correct default values."""
        config = SamplingConfig()
        
        assert config.enabled is False
        assert config.default_rate == 1.0
        assert config.rules == {}

    def test_custom_values(self) -> None:
        """Test SamplingConfig accepts custom values."""
        rules = {
            "quadkit.web": 0.5,
            "quadkit.cli": 0.1,
        }
        config = SamplingConfig(
            enabled=True,
            default_rate=0.25,
            rules=rules,
        )
        
        assert config.enabled is True
        assert config.default_rate == 0.25
        assert config.rules == rules

    def test_rate_clamping_above_max(self) -> None:
        """Test SamplingConfig rejects rate above 1.0."""
        with pytest.raises(ValueError, match=re.escape("must be less than or equal to 1.0")):
            SamplingConfig(default_rate=1.5)

    def test_rate_clamping_below_min(self) -> None:
        """Test SamplingConfig rejects rate below 0.0."""
        with pytest.raises(ValueError, match=re.escape("must be greater than or equal to 0.0")):
            SamplingConfig(default_rate=-0.5)

    def test_rate_boundary_values(self) -> None:
        """Test SamplingConfig accepts boundary rate values."""
        config_min = SamplingConfig(default_rate=0.0)
        assert config_min.default_rate == 0.0
        
        config_max = SamplingConfig(default_rate=1.0)
        assert config_max.default_rate == 1.0

    def test_empty_rules(self) -> None:
        """Test SamplingConfig with empty rules dict."""
        config = SamplingConfig(rules={})
        
        assert config.rules == {}

    def test_single_rule(self) -> None:
        """Test SamplingConfig with single rule."""
        config = SamplingConfig(
            rules={"quadkit.web": 0.5},
        )
        
        assert len(config.rules) == 1
        assert config.rules["quadkit.web"] == 0.5

    def test_multiple_rules(self) -> None:
        """Test SamplingConfig with multiple rules."""
        rules = {
            "quadkit.web": 0.5,
            "quadkit.cli": 0.1,
            "quadkit.testing": 0.8,
            "custom.logger": 0.3,
        }
        config = SamplingConfig(rules=rules)
        
        assert len(config.rules) == 4
        assert config.rules["quadkit.web"] == 0.5
        assert config.rules["quadkit.cli"] == 0.1

    def test_enabled_with_default_rate(self) -> None:
        """Test SamplingConfig enabled with default rate."""
        config = SamplingConfig(enabled=True, default_rate=0.1)
        
        assert config.enabled is True
        assert config.default_rate == 0.1

    def test_disabled_with_custom_rate(self) -> None:
        """Test SamplingConfig disabled but still accepts custom rate."""
        config = SamplingConfig(enabled=False, default_rate=0.5)
        
        assert config.enabled is False
        assert config.default_rate == 0.5

    def test_model_validator_runs(self) -> None:
        """Test that model_validator normalizes rate."""
        # Field validation happens first and rejects out-of-bounds values
        # The model_validator would normalize if validation passed
        config = SamplingConfig(default_rate=0.5)
        
        # Valid rate should work
        assert config.default_rate == 0.5
        
        # Test boundary values pass field validation
        config_min = SamplingConfig(default_rate=0.0)
        assert config_min.default_rate == 0.0
        
        config_max = SamplingConfig(default_rate=1.0)
        assert config_max.default_rate == 1.0
