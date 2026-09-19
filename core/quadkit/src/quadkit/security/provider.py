"""DI Provider for core security primitives.

Registers transport-agnostic security utilities as singletons:
:class:`~quadkit.security.guards.GuardChainImpl`,
:class:`~quadkit.security.sanitization.InputSanitizer`, and
:class:`~quadkit.security.config.InputSanitizerConfig`.

HTTP security middleware (CORS, CSRF, CSP, response headers) is registered
by ``WebProvider`` in ``quadkit-web`` — it does not belong here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from quadkit.contracts.core.health import HealthCheckResult, HealthStatus
from quadkit.contracts.security import (
    HasherProtocol,
    InputSanitizerProtocol,
    KeyDerivationProtocol,
)
from quadkit.di.provider import Provider, ProviderPriority
from quadkit.logging import get_logger
from quadkit.security.config import HashingConfig, InputSanitizerConfig, SecurityConfig
from quadkit.security.guards.chain import GuardChainImpl
from quadkit.security.hashing import PBKDF2KDF, Blake2bHasher, Sha256Hasher
from quadkit.security.sanitization.sanitizer import InputSanitizer

if TYPE_CHECKING:
    from quadkit.contracts.core.di import (
        BootContainerProtocol,
        ContainerRegistrarProtocol,
    )

logger = get_logger(__name__)


class SecurityProvider(Provider):
    """Core security primitives DI provider.

    Registers:
    - :class:`~quadkit.security.config.SecurityConfig`
    - :class:`~quadkit.security.config.InputSanitizerConfig`
    - :class:`~quadkit.security.config.HashingConfig`
    - :class:`~quadkit.security.sanitization.InputSanitizer` (as both
      concrete and :class:`~quadkit.contracts.security.InputSanitizerProtocol`)
    - :class:`~quadkit.security.hashing.Sha256Hasher` as the default
      :class:`~quadkit.contracts.security.HasherProtocol`
    - :class:`~quadkit.security.hashing.PBKDF2KDF` as the default
      :class:`~quadkit.contracts.security.KeyDerivationProtocol`
    - :class:`~quadkit.security.guards.GuardChainImpl` (empty chain; consumers
      may resolve it and extend with ``.add()``)
    """

    name = "security"
    priority = ProviderPriority.INFRASTRUCTURE

    def __init__(
        self,
        config: SecurityConfig | InputSanitizerConfig | None = None,
    ) -> None:
        super().__init__()
        if isinstance(config, SecurityConfig):
            self._config = config
        elif isinstance(config, InputSanitizerConfig):
            self._config = SecurityConfig(sanitization=config)
        else:
            self._config = SecurityConfig()

        self._input_sanitizer: InputSanitizer | None = None
        self._guard_chain: GuardChainImpl | None = None
        self._hasher: Sha256Hasher | None = None
        self._key_derivation: PBKDF2KDF | None = None

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        """Register core security components."""
        hashing_config = self._config.hashing
        sanitizer_config = self._config.sanitization

        container.singleton(SecurityConfig, self._config)
        container.singleton(InputSanitizerConfig, sanitizer_config)
        container.singleton(HashingConfig, hashing_config)

        _sanitizer = InputSanitizer(sanitizer_config)
        container.singleton(InputSanitizer, _sanitizer)
        container.singleton(InputSanitizerProtocol, _sanitizer)

        hasher = (
            Sha256Hasher()
            if hashing_config.default_hasher == "sha256"
            else Blake2bHasher(digest_size=hashing_config.blake2b_digest_size)
        )
        container.singleton(Sha256Hasher, Sha256Hasher())
        container.singleton(
            Blake2bHasher,
            Blake2bHasher(digest_size=hashing_config.blake2b_digest_size),
        )
        container.singleton(HasherProtocol, hasher)

        key_derivation = PBKDF2KDF(
            algorithm=hashing_config.algorithm,
            hash_name=hashing_config.default_hasher,
            iterations=hashing_config.iterations,
            salt_length=hashing_config.salt_length,
            dklen=hashing_config.dklen,
        )
        container.singleton(PBKDF2KDF, key_derivation)
        container.singleton(KeyDerivationProtocol, key_derivation)

        container.singleton(GuardChainImpl, GuardChainImpl())

        logger.debug("security_provider_registered")

    async def boot(self, container: BootContainerProtocol) -> None:
        """Eagerly resolve singletons and install ambient hasher."""
        self._input_sanitizer = await container.resolve(InputSanitizer)
        self._guard_chain = await container.resolve(GuardChainImpl)
        self._hasher = await container.resolve(HasherProtocol)
        self._key_derivation = await container.resolve(KeyDerivationProtocol)

        from quadkit.security.hashing import ambient as hashing_ambient

        hashing_ambient.install(self._hasher)

        logger.debug("security_provider_booted")

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Report health of the security provider.

        The core security provider is stateless — it holds no external
        connections and no background tasks.  This check always returns
        :attr:`~quadkit.contracts.core.health.HealthStatus.HEALTHY`.

        Args:
            timeout: Unused; included for interface consistency.

        Returns:
            Healthy result.
        """
        return HealthCheckResult(
            component="security",
            status=HealthStatus.HEALTHY,
            message="Core security primitives operational — no external dependencies",
        )

    async def shutdown(self) -> None:
        """No resources to release."""


__all__ = ["SecurityProvider"]
