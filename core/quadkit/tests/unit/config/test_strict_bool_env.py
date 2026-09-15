"""Tests for strict bool coercion of environment-variable config values.

A bool field receiving an uncoercible string (e.g. ``QK_DEBUG=garbage``)
must fail loudly at config-load time — silently storing the string would
leave a truthy value in a ``bool``-typed field (and thus, e.g., enable
debug mode in production).

Numeric strings (``0``/``1``) must coerce to real ``bool`` values, not
int, so that ``isinstance(config.debug, bool)`` holds after loading.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

import pytest

from quadkit.config import BaseConfig


@dataclass(init=False)
class _BoolCfg(BaseConfig):
    """Minimal config used to exercise env-var bool coercion."""

    flag: bool = False
    maybe: Optional[bool] = None


def _load() -> _BoolCfg:
    return _BoolCfg.from_yaml("does-not-exist-for-bool-test.yaml")


class TestStrictBoolEnv:
    """Env-var values for bool fields must coerce strictly."""

    @pytest.fixture(autouse=True)
    def _clean_env(self):
        for key in ("QK_FLAG", "QK_MAYBE"):
            os.environ.pop(key, None)
        yield
        for key in ("QK_FLAG", "QK_MAYBE"):
            os.environ.pop(key, None)

    def test_garbage_string_raises(self):
        """Uncoercible strings must raise, not become truthy strings."""
        os.environ["QK_FLAG"] = "garbage"
        with pytest.raises(ValueError, match="to bool"):
            _load()

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("true", True),
            ("TRUE", True),
            ("yes", True),
            ("on", True),
            ("1", True),
            ("false", False),
            ("FALSE", False),
            ("no", False),
            ("off", False),
            ("0", False),
        ],
    )
    def test_canonical_values(self, raw, expected):
        os.environ["QK_FLAG"] = raw
        cfg = _load()
        assert cfg.flag is expected
        assert isinstance(cfg.flag, bool)

    def test_int_values_normalize_to_bool(self):
        """``1``/``0`` arrive as ints from the env source; normalize them."""
        # Simulate the int that EnvironmentConfigSource produces.
        cfg = _BoolCfg(flag=1, maybe=0)
        assert cfg.flag is True
        assert cfg.maybe is False

    def test_optional_bool_garbage_raises(self):
        """Optional[bool] fields get the same strict treatment."""
        os.environ["QK_MAYBE"] = "bogus"
        with pytest.raises(ValueError, match="to bool"):
            _load()

    def test_bool_fields_still_accept_real_bools(self):
        cfg = _BoolCfg(flag=True, maybe=False)
        assert cfg.flag is True
        assert cfg.maybe is False
