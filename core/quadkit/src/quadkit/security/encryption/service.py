"""AES-256-GCM encryption service for field-level encryption of sensitive data."""

from __future__ import annotations

import os

from quadkit.logging import get_logger
from quadkit.result import Err, Ok, Result
from quadkit.security.exceptions import DecryptionError, EncryptionError

logger = get_logger(__name__)

try:
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

    _CRYPTOGRAPHY_AVAILABLE = True
except ImportError:  # pragma: no cover
    _CRYPTOGRAPHY_AVAILABLE = False


class EncryptionService:
    """Field-level encryption service using AES-256-GCM.

    Provides authenticated encryption for sensitive fields (PII, payment data).
    Each encryption operation generates a random 96-bit nonce; the ciphertext
    format is: [nonce (12 bytes) | tag (16 bytes) | encrypted data].

    Requires the ``cryptography`` package::

        pip install quadkit[security]

    Args:
        key: 32-byte AES-256 key (generated or provided).
             If None, a random key is generated.
        secret_key: Human-readable passphrase. Derived to a 32-byte key
            via SHA-256.  Ignored when ``key`` is provided.
    """

    NONCE_SIZE = 12  # 96 bits for GCM (recommended)
    TAG_SIZE = 16  # 128 bits for GCM
    KEY_SIZE = 32  # 256 bits

    def __init__(
        self,
        key: bytes | None = None,
        secret_key: str | None = None,
    ) -> None:
        """Initialize encryption service.

        Args:
            key: 32-byte AES-256 key. Generated randomly when both ``key``
                and ``secret_key`` are omitted.
            secret_key: Human-readable passphrase. Derived to a 32-byte key
                via SHA-256.  Ignored when ``key`` is provided.

        Raises:
            ImportError: If the ``cryptography`` package is not installed.
            EncryptionError: If an explicit ``key`` has an invalid length.
        """
        if not _CRYPTOGRAPHY_AVAILABLE:  # pragma: no cover
            raise ImportError(
                "EncryptionService requires the 'cryptography' package. "
                "Install it with: pip install quadkit[security]"
            )

        import hashlib

        if key is not None:
            if len(key) != self.KEY_SIZE:
                raise EncryptionError(
                    f"Key must be {self.KEY_SIZE} bytes; got {len(key)}"
                )
            self._key = key
        elif secret_key is not None:
            self._key = hashlib.sha256(secret_key.encode("utf-8")).digest()
        else:
            self._key = os.urandom(self.KEY_SIZE)

    def encrypt(self, plaintext: str, aad: bytes | None = None) -> str:
        """Encrypt plaintext and return hex-encoded ciphertext.

        Args:
            plaintext: Text to encrypt.
            aad: Optional additional authenticated data.

        Returns:
            Hex-encoded ciphertext (nonce + tag + encrypted data).

        Raises:
            EncryptionError: If encryption fails.
        """
        result = self._encrypt_sync(plaintext, aad)
        if result.is_ok():
            return result.unwrap()
        raise result.unwrap_err()

    def decrypt(self, ciphertext_hex: str, aad: bytes | None = None) -> str:
        """Decrypt hex-encoded ciphertext and return plaintext.

        Args:
            ciphertext_hex: Hex-encoded ciphertext produced by :meth:`encrypt`.
            aad: Optional additional authenticated data (must match original).

        Returns:
            Decrypted plaintext.

        Raises:
            DecryptionError: If decryption or authentication fails.
        """
        result = self._decrypt_sync(ciphertext_hex, aad)
        if result.is_ok():
            return result.unwrap()
        raise result.unwrap_err()

    def _encrypt_sync(
        self, plaintext: str, aad: bytes | None = None
    ) -> Result[str, EncryptionError]:
        """Synchronously encrypt plaintext to hex-encoded ciphertext."""
        try:
            nonce = os.urandom(self.NONCE_SIZE)
            cipher = Cipher(
                algorithms.AES(self._key),
                modes.GCM(nonce),
                backend=default_backend(),
            )
            encryptor = cipher.encryptor()
            if aad:
                encryptor.authenticate_additional_data(aad)
            ciphertext = (
                encryptor.update(plaintext.encode("utf-8")) + encryptor.finalize()
            )
            result_bytes = nonce + encryptor.tag + ciphertext
            logger.debug("encrypted_field", plaintext_len=len(plaintext))
            return Ok(result_bytes.hex())
        except (TypeError, ValueError, OSError) as e:
            logger.error("encryption_failed", error=str(e))
            return Err(EncryptionError(f"Encryption failed: {e}"))

    def _decrypt_sync(
        self, ciphertext_hex: str, aad: bytes | None = None
    ) -> Result[str, DecryptionError]:
        """Decrypt hex-encoded ciphertext to plaintext."""
        try:
            ciphertext_bytes = bytes.fromhex(ciphertext_hex)
            min_size = self.NONCE_SIZE + self.TAG_SIZE
            if len(ciphertext_bytes) < min_size:
                return Err(
                    DecryptionError(
                        f"Ciphertext too short: {len(ciphertext_bytes)} < {min_size}"
                    )
                )
            nonce = ciphertext_bytes[: self.NONCE_SIZE]
            tag = ciphertext_bytes[self.NONCE_SIZE : self.NONCE_SIZE + self.TAG_SIZE]
            encrypted_data = ciphertext_bytes[self.NONCE_SIZE + self.TAG_SIZE :]

            cipher = Cipher(
                algorithms.AES(self._key),
                modes.GCM(nonce, tag),
                backend=default_backend(),
            )
            decryptor = cipher.decryptor()
            if aad:
                decryptor.authenticate_additional_data(aad)
            plaintext = (
                decryptor.update(encrypted_data) + decryptor.finalize()
            ).decode("utf-8")
            logger.debug("decrypted_field", plaintext_len=len(plaintext))
            return Ok(plaintext)
        except ValueError as e:
            logger.error("decryption_failed", error=str(e))
            return Err(DecryptionError(f"Authentication tag verification failed: {e}"))
        except (TypeError, AttributeError) as e:
            logger.error("decryption_failed", error=str(e))
            return Err(DecryptionError(f"Decryption failed: {e}"))
        except Exception as e:  # noqa: BLE001 — catch cryptography.exceptions.InvalidTag and other auth failures
            logger.error("decryption_failed", error=str(e))
            return Err(DecryptionError(f"Decryption failed: {e}"))

    @staticmethod
    def generate_key() -> bytes:
        """Generate a random 256-bit (32-byte) AES key.

        Returns:
            32-byte key suitable for AES-256-GCM.
        """
        return os.urandom(EncryptionService.KEY_SIZE)


__all__ = ["EncryptionService"]
