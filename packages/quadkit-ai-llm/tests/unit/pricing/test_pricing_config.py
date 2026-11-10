"""Tests for pricing configuration parsing and source building."""

from __future__ import annotations

import pytest

from quadkit.ai.llm.config import ClientConfig, PricingConfig, PricingSourceConfig


class TestPricingConfig:
    """Tests for PricingConfig and PricingSourceConfig."""

    def test_model_validate_coerces_nested_sources(self) -> None:
        cfg = PricingConfig.model_validate(
            {
                "enabled": True,
                "cache_ttl": 43200,
                "sources": [
                    {"type": "openrouter"},
                    {"type": "litellm"},
                    {"type": "json", "file_path": "pricing/custom.json"},
                    {
                        "type": "static",
                        "models": {
                            "internal": {
                                "prompt_per_1m": 0.5,
                                "completion_per_1m": 1.5,
                                "provider": "custom",
                            }
                        },
                    },
                ],
            }
        )

        assert cfg.enabled is True
        assert cfg.cache_ttl == 43200
        sources = cfg.build_sources()
        assert [type(s).__name__ for s in sources] == [
            "OpenRouterPricingSource",
            "APIPricingSource",
            "JSONFilePricingSource",
            "StaticPricingSource",
        ]

    def test_client_config_from_dict_coerces_pricing(self) -> None:
        cfg = ClientConfig.from_dict(
            {"pricing": {"sources": [{"type": "openrouter"}]}}
        )

        assert isinstance(cfg.pricing, PricingConfig)
        sources = cfg.pricing.build_sources()
        assert [type(s).__name__ for s in sources] == [
            "OpenRouterPricingSource"
        ]

    def test_empty_sources_build_defaults(self) -> None:
        cfg = ClientConfig.from_dict({"pricing": {"sources": []}})

        sources = cfg.pricing.build_sources()
        assert [type(s).__name__ for s in sources] == [
            "OpenRouterPricingSource",
            "APIPricingSource",
        ]

    def test_unknown_source_type_raises(self) -> None:
        cfg = ClientConfig.from_dict(
            {"pricing": {"sources": [{"type": "bogus"}]}}
        )

        with pytest.raises(ValueError, match="Unknown pricing source type"):
            cfg.pricing.build_sources()

    def test_json_source_requires_file_path(self) -> None:
        cfg = ClientConfig.from_dict(
            {"pricing": {"sources": [{"type": "json"}]}}
        )

        with pytest.raises(ValueError, match="file_path"):
            cfg.pricing.build_sources()

    def test_source_config_defaults(self) -> None:
        cfg = PricingSourceConfig(type="openrouter")

        assert cfg.type == "openrouter"
        assert cfg.endpoint is None
        assert cfg.file_path is None
        assert cfg.timeout == 10.0
        assert cfg.models == {}
