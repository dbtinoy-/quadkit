"""Tests for core security hashing primitives."""

from __future__ import annotations

import hashlib

import pytest

from quadkit.contracts.security import HasherProtocol, KeyDerivationProtocol
from quadkit.di.container import Container
from quadkit.security.config import HashingConfig, SecurityConfig
from quadkit.security.hashing import Blake2bHasher, PBKDF2KDF, Sha256Hasher
from quadkit.security.provider import SecurityProvider


class TestSecurityContracts:
    """Tests for security hashing contracts."""

    def test_hashing_protocols_are_importable(self) -> None:
        """The new hashing protocols should be exported from contracts."""
        assert HasherProtocol.__name__ == "HasherProtocol"
        assert KeyDerivationProtocol.__name__ == "KeyDerivationProtocol"


class TestDigestHashers:
    """Tests for the built-in digest hashers."""

    @pytest.mark.asyncio
    async def test_sha256_hasher_is_deterministic(self) -> None:
        """SHA-256 hashing should return a stable hex digest."""
        hasher = Sha256Hasher()
        digest = await hasher.hash("quadkit")

        assert digest == hashlib.sha256(b"quadkit").hexdigest()
        assert await hasher.verify("quadkit", digest) is True
        assert await hasher.verify("quadkit!", digest) is False

    @pytest.mark.asyncio
    async def test_blake2b_hasher_is_deterministic(self) -> None:
        """BLAKE2b hashing should return a stable hex digest."""
        hasher = Blake2bHasher()
        digest = await hasher.hash("quadkit")

        assert digest == hashlib.blake2b(b"quadkit").hexdigest()
        assert await hasher.verify("quadkit", digest) is True
        assert await hasher.verify("quadkit!", digest) is False


class TestPBKDF2KDF:
    """Tests for the PBKDF2 key derivation helper."""

    @pytest.mark.asyncio
    async def test_pbkdf2_uses_stable_encoded_format(self) -> None:
        """PBKDF2 output should encode the algorithm, iterations, salt, and key."""
        salt = bytes.fromhex("00112233445566778899aabbccddeeff")
        kdf = PBKDF2KDF(iterations=5_000, salt_length=len(salt))

        encoded = await kdf.derive("quadkit", salt=salt)
        parts = encoded.split("$")

        assert parts[0] == "pbkdf2_sha256"
        assert parts[1] == "5000"
        assert parts[2] == salt.hex()
        assert len(parts[3]) == 64
        assert await kdf.verify("quadkit", encoded) is True
        assert await kdf.verify("quadkit!", encoded) is False


class TestSecurityConfig:
    """Tests for security hashing configuration."""

    def test_security_config_exposes_nested_hashing(self) -> None:
        """Security config should expose a nested hashing config section."""
        config = SecurityConfig()

        assert isinstance(config.hashing, HashingConfig)
        assert config.hashing.algorithm == "pbkdf2_sha256"
        assert config.hashing.iterations > 0


class TestSecurityProviderHashingDefaults:
    """Tests for provider registration of hashing defaults."""

    @pytest.mark.asyncio
    async def test_provider_registers_default_hashers(self) -> None:
        """SecurityProvider should register the default hasher and KDF."""
        container = Container()
        provider = SecurityProvider()

        await provider.register(container)
        await provider.boot(container)

        hasher = await container.resolve(HasherProtocol)
        kdf = await container.resolve(KeyDerivationProtocol)

        assert isinstance(hasher, Sha256Hasher)
        assert isinstance(kdf, PBKDF2KDF)
