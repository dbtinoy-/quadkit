"""Field-level encryption service with AES-256-GCM.

Provides authenticated encryption for sensitive fields (PII, payment data).
Uses `cryptography.hazmat.primitives.ciphers.Cipher` for AES-256-GCM
with automatic nonce management.

Requires the ``cryptography`` package.  Install with::

    pip install quadkit[security]
"""

from __future__ import annotations

from quadkit.security.encryption.service import EncryptionService

__all__ = ["EncryptionService"]
