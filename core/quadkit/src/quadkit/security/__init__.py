"""Security primitives for the Quadkit Framework.

Transport-agnostic security utilities: guards, encryption, secrets,
and input sanitization.

HTTP-specific middleware (CORS, CSRF, CSP, HSTS, security response headers)
lives in ``quadkit-web`` at ``quadkit.web.security``.
"""

from __future__ import annotations

# -- Exceptions (Task 1) -----------------------------------------------------
from quadkit.contracts.security import SecretNotFoundError as SecretNotFoundError

# -- Hashing (Task 3) --------------------------------------------------------
from quadkit.security.config import HashingConfig as HashingConfig
from quadkit.security.config import SecurityConfig as SecurityConfig

# -- Decorators (Task 2) -----------------------------------------------------
from quadkit.security.decorators import sanitize_input as sanitize_input

# -- Encryption (Task 2) -----------------------------------------------------
from quadkit.security.encryption import EncryptionService as EncryptionService
from quadkit.security.events import CsrfViolationEvent as CsrfViolationEvent
from quadkit.security.events import SecretRotatedEvent as SecretRotatedEvent
from quadkit.security.events import (
    SecurityGuardDeniedEvent as SecurityGuardDeniedEvent,
)

# -- Domain events (Task 2) --------------------------------------------------
from quadkit.security.events import ThreatDetectedEvent as ThreatDetectedEvent
from quadkit.security.exceptions import DecryptionError as DecryptionError
from quadkit.security.exceptions import EncryptionError as EncryptionError
from quadkit.security.exceptions import MiddlewareGuardError as MiddlewareGuardError
from quadkit.security.exceptions import SecretAccessError as SecretAccessError
from quadkit.security.exceptions import SecretError as SecretError
from quadkit.security.exceptions import SecurityError as SecurityError

# -- Guards (Task 2) ---------------------------------------------------------
from quadkit.security.guards import GuardChainImpl as GuardChainImpl
from quadkit.security.guards import use_guards as use_guards
from quadkit.security.hashing import PBKDF2KDF as PBKDF2KDF
from quadkit.security.hashing import Blake2bHasher as Blake2bHasher
from quadkit.security.hashing import Sha256Hasher as Sha256Hasher

# -- Hooks (Task 2) ----------------------------------------------------------
from quadkit.security.hooks import SecurityGuardBlockedHook as SecurityGuardBlockedHook
from quadkit.security.hooks import SecurityGuardPassedHook as SecurityGuardPassedHook
from quadkit.security.hooks import (
    SecurityThreatDetectedHook as SecurityThreatDetectedHook,
)

# -- Provider (Task 2) -------------------------------------------------------
from quadkit.security.provider import SecurityProvider as SecurityProvider

# -- Sanitization (Task 2) ---------------------------------------------------
from quadkit.security.sanitization import InputSanitizer as InputSanitizer
from quadkit.security.secrets import EnvSecretStore as EnvSecretStore
from quadkit.security.secrets import FileSecretStore as FileSecretStore

# -- Secrets (Task 2) --------------------------------------------------------
from quadkit.security.secrets import InMemorySecretStore as InMemorySecretStore
from quadkit.security.secrets import SecretValue as SecretValue

__all__ = [
    "PBKDF2KDF",
    "Blake2bHasher",
    "CsrfViolationEvent",
    "DecryptionError",
    "EncryptionError",
    "EncryptionService",
    "EnvSecretStore",
    "FileSecretStore",
    "GuardChainImpl",
    "HashingConfig",
    "InMemorySecretStore",
    "InputSanitizer",
    "MiddlewareGuardError",
    "SecretAccessError",
    "SecretError",
    "SecretNotFoundError",
    "SecretRotatedEvent",
    "SecretValue",
    "SecurityConfig",
    "SecurityError",
    "SecurityGuardBlockedHook",
    "SecurityGuardDeniedEvent",
    "SecurityGuardPassedHook",
    "SecurityProvider",
    "SecurityThreatDetectedHook",
    "Sha256Hasher",
    "ThreatDetectedEvent",
    "sanitize_input",
    "use_guards",
]
