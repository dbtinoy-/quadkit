"""Security contracts for Quadkit Framework.

Provides protocols and types for security-related concerns, including
secret management, guards, input sanitization, and response headers.
"""

from __future__ import annotations

from quadkit.contracts.exceptions.components import (
    SecretNotFoundError,
)
from quadkit.contracts.exceptions.security import (
    CORSViolationError,
    GuardDeniedError,
    InputSanitizationError,
    SecretAccessError,
    SecurityError,
)
from quadkit.contracts.security.protocols import (
    CORSProtocol,
    CSPProtocol,
    CSRFProtocol,
    EncryptionProtocol,
    GuardChainProtocol,
    HasherProtocol,
    InputSanitizerProtocol,
    KeyDerivationProtocol,
    SecurityHeadersProtocol,
)
from quadkit.contracts.security.rotation import SecretRotationPolicy
from quadkit.contracts.security.secrets import (
    SecretStoreProtocol,
)
from quadkit.contracts.security.stores import AsyncSecretStoreProtocol
from quadkit.contracts.security.url_safety import (
    HostResolver,
    collect_safe_addresses,
    is_safe_url_for_request,
    resolve_hostname,
)

__all__ = [
    "AsyncSecretStoreProtocol",
    "CORSProtocol",
    "CORSViolationError",
    "CSPProtocol",
    "CSRFProtocol",
    "EncryptionProtocol",
    "GuardChainProtocol",
    "GuardDeniedError",
    "HasherProtocol",
    "HostResolver",
    "InputSanitizationError",
    "InputSanitizerProtocol",
    "KeyDerivationProtocol",
    "SecretAccessError",
    "SecretNotFoundError",
    "SecretRotationPolicy",
    "SecretStoreProtocol",
    "SecurityError",
    "SecurityHeadersProtocol",
    "collect_safe_addresses",
    "is_safe_url_for_request",
    "resolve_hostname",
]
