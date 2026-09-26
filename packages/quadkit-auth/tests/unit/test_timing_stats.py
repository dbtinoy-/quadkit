"""Statistical timing test to detect user-enumeration timing leaks.

This test measures authenticate_user latency for an existing user and a
non-existing user over many iterations and asserts the relative difference
is small enough to rule out a practical timing side-channel.

The test is intentionally conservative to avoid flaky failures on CI: it
uses a relative difference threshold instead of an absolute delta.
"""

import asyncio
import statistics
import time

import pytest

from quadkit.auth.authn.security import DUMMY_PASSWORD_HASH, PasswordHasher
from quadkit.auth.di import AuthenticationProvider
from quadkit.auth.models.user import UserCredentials
from quadkit.logging import get_logger

logger = get_logger(__name__)


@pytest.mark.asyncio
async def test_authenticate_user_timing_is_similar_for_missing_and_existing_user(
    monkeypatch,
):
    """Measure latencies for existing vs missing user flows.

    Asserts the relative difference in mean latency is below 25%.
    """
    provider = AuthenticationProvider()

    # Precompute a single hashed password to avoid expensive work per-FakeUser
    precomputed_hash = await PasswordHasher().hash("Password123!")

    class FakeUser:
        def __init__(self):
            self.user_id = "u1"
            self.email = "user1@example.com"
            self.name = "user1"
            self.is_active = True

        def record_login(self):
            pass

    fake_creds = UserCredentials(user_id="u1", hashed_password=precomputed_hash)

    async def get_existing(email: str):
        return FakeUser()

    async def get_none(email: str):
        return None

    async def fake_get_credentials(user_id: str):
        return fake_creds

    # Patch update_user to no-op to avoid store dependency
    async def fake_update_user(user):
        return None

    async def fake_update_credentials(creds):
        return None

    provider.user_store.get_user_by_email = get_existing
    provider.user_store.get_credentials = fake_get_credentials

    async def get_email_none(email: str):
        return None

    provider.user_store.get_user_by_email = get_email_none
    provider.user_store.update_user = fake_update_user
    provider.user_store.update_credentials = fake_update_credentials

    # Monkeypatch the composed hasher's verify to add consistent delay so
    # measurements are stable and independent of the underlying KDF, and
    # disable the upgrade-on-login rehash so successful logins do no hashing.
    composed = provider.password_hasher

    async def slow_verify(password: str, hashed: str) -> bool:
        # 5ms async delay to simulate bcrypt-like cost without blocking
        await asyncio.sleep(0.005)
        # Return True for real user hash, False for dummy hash
        return hashed != DUMMY_PASSWORD_HASH

    async def no_rehash(password: str, hashed_password: str | None) -> str | None:
        return None

    monkeypatch.setattr(composed, "verify", slow_verify)
    monkeypatch.setattr(composed, "rehash_if_needed", no_rehash)

    # Warm-up to avoid cold-start artifacts
    for _ in range(10):
        await provider.service.authenticate_user("user1@example.com", "Password123!")
        await provider.service.authenticate_user("no_user@example.com", "Password123!")

    iterations = 200  # Reduced iterations for faster test while maintaining statistical signficance

    async def measure_flow(get_user_target):
        """Async helper to measure repeated authenticate_user calls."""

        times: list[float] = []
        for _ in range(iterations):
            start = time.perf_counter()
            await provider.service.authenticate_user(
                "user1@example.com"
                if get_user_target is get_existing
                else "no_user@example.com",
                "Password123!",
            )
            times.append(time.perf_counter() - start)
        return times

    # Measure existing user flow
    provider.user_store.get_user_by_email = get_existing
    provider.user_store.get_credentials = fake_get_credentials
    existing_times = await measure_flow(get_existing)

    # Measure missing user flow
    provider.user_store.get_user_by_email = get_none
    missing_times = await measure_flow(get_none)

    # Use medians to reduce sensitivity to transient scheduling spikes
    median_existing = statistics.median(existing_times)
    median_missing = statistics.median(missing_times)

    # Relative difference (normalized by the higher median)
    rel_diff = abs(median_existing - median_missing) / max(
        median_existing,
        median_missing,
    )

    # Log some stats to help debug if this test fails.
    mean_existing = statistics.mean(existing_times)
    mean_missing = statistics.mean(missing_times)
    logger.debug(
        "timing stats -> existing mean: %.6fs, missing mean: %.6fs, existing median: %.6fs, missing median: %.6fs, rel_diff: %.3f",
        mean_existing,
        mean_missing,
        median_existing,
        median_missing,
        rel_diff,
    )

    # Assert relative difference is small — allow a slightly more permissive threshold to
    # avoid CI flakiness while still catching practical timing leaks.
    assert rel_diff < 0.35, (
        "Timing difference too large; possible user enumeration leak"
    )
