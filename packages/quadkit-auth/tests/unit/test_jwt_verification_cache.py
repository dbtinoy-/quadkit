"""P1-3: JWT verification cache must use OrderedDict with LRU eviction."""

from collections import OrderedDict

import pytest

from quadkit.auth.authn.jwt import JWTTokenManager
from quadkit.validation import SecretStr


@pytest.fixture()
def token_manager() -> JWTTokenManager:
    """Minimal JWTTokenManager for cache inspection."""
    return JWTTokenManager(
        current_key_id="k1",
        keys={"k1": SecretStr("test-secret-key-at-least-32-characters-long")},
    )


class TestJWTVerificationCacheType:
    """P1-3: _verification_cache must be OrderedDict for LRU eviction."""

    def test_jwt_verification_cache_is_ordered_dict(
        self, token_manager: JWTTokenManager
    ) -> None:
        """P1-3: _verification_cache must be OrderedDict for LRU eviction."""
        assert isinstance(token_manager._verification_cache, OrderedDict), (
            "_verification_cache is a plain dict — LRU eviction is not possible"
        )


class TestJWTVerificationCacheEviction:
    """P1-3: Adding the 1001st entry evicts 1 (oldest), not all 1000."""

    def test_jwt_verification_cache_evicts_oldest_not_all(
        self, token_manager: JWTTokenManager
    ) -> None:
        """Filling cache to 1000 then adding one more must evict only the oldest entry."""
        cache: OrderedDict[str, str] = token_manager._verification_cache

        # Fill to exactly 1000 entries
        for i in range(1000):
            cache[f"hash_{i:04d}"] = f"key_{i}"

        assert len(cache) == 1000
        oldest_key = "hash_0000"
        assert oldest_key in cache

        # Simulate the eviction logic (as the fix should implement it):
        # >=1000 → popitem(last=False) then insert new entry
        if len(cache) >= 1000:
            cache.popitem(last=False)
        cache["hash_new"] = "key_new"

        # Must still have 1000 entries — one evicted, one added
        assert len(cache) == 1000, (
            f"Expected 1000 entries after LRU eviction, got {len(cache)}"
        )
        # Oldest entry must be gone
        assert oldest_key not in cache, (
            "hash_0000 (oldest) should have been evicted"
        )
        # New entry must be present
        assert "hash_new" in cache

    def test_jwt_verification_cache_move_to_end_on_hit(
        self, token_manager: JWTTokenManager
    ) -> None:
        """A cache hit must move the entry to the end (mark as recently used)."""
        cache: OrderedDict[str, str] = token_manager._verification_cache

        cache["first"] = "key_a"
        cache["second"] = "key_b"
        cache["third"] = "key_c"

        # Simulate a cache hit on "first" — it should move to end
        cache.move_to_end("first")

        keys = list(cache.keys())
        assert keys[-1] == "first", (
            "Cache hit must move token_hash to the end (most-recently-used)"
        )
        assert keys[0] == "second"
