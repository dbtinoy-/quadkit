"""Embedding configs must not leak api_key through repr (audit §10 F4)."""

from __future__ import annotations

import pytest


class TestEmbeddingConfigSecrets:
    @pytest.mark.parametrize(
        "config_cls",
        [
            "OpenAIEmbeddingConfig",
            "CohereEmbeddingConfig",
            "VoyageEmbeddingConfig",
            "JinaEmbeddingConfig",
        ],
    )
    def test_repr_masks_api_key(self, config_cls: str) -> None:
        import importlib

        mod = importlib.import_module("quadkit.ai.llm.embedding.config")
        cls = getattr(mod, config_cls)
        cfg = cls(api_key="super-secret-key-0123456789")
        assert "super-secret-key-0123456789" not in repr(cfg)