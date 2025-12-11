"""
Token encryption service using Fernet symmetric encryption.

Provides secure storage for sensitive data like GitHub access tokens.
"""

import os
from functools import lru_cache
from typing import TYPE_CHECKING, Any, Optional

from core.logging import get_logger

logger = get_logger("security.encryption")

# Try to import cryptography, provide fallback message if not available
if TYPE_CHECKING:
    from cryptography.fernet import Fernet, InvalidToken
else:
    try:
        from cryptography.fernet import Fernet, InvalidToken

        CRYPTOGRAPHY_AVAILABLE = True
    except ImportError:
        CRYPTOGRAPHY_AVAILABLE = False
        Fernet = None  # type: ignore[assignment]
        InvalidToken = Exception  # type: ignore[assignment]


class EncryptionError(Exception):
    """Raised when encryption/decryption fails."""

    pass


class TokenEncryption:
    """
    Fernet-based encryption for sensitive tokens.

    Fernet guarantees that data encrypted using it cannot be read
    or tampered with without the key. It uses AES-128-CBC with
    HMAC for authentication.

    Usage:
        encryption = TokenEncryption()

        # Encrypt a token
        encrypted = encryption.encrypt("ghp_xxxx...")

        # Decrypt a token
        decrypted = encryption.decrypt(encrypted)

    Environment:
        TOKEN_ENCRYPTION_KEY: Base64-encoded 32-byte Fernet key
    """

    _instance: Optional["TokenEncryption"] = None
    _fernet: Any | None = None  # Fernet type when available
    _initialized: bool = False
    _available: bool = False

    def __new__(cls) -> "TokenEncryption":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        # Prevent re-initialization
        pass

    def initialize(self, key: str | None = None) -> bool:
        """
        Initialize encryption with the provided or environment key.

        Args:
            key: Optional Fernet key (uses TOKEN_ENCRYPTION_KEY env var if not provided)

        Returns:
            True if encryption is available, False otherwise
        """
        if self._initialized:
            return self._available

        if not CRYPTOGRAPHY_AVAILABLE:
            logger.warning(
                "encryption_unavailable",
                reason="cryptography package not installed",
            )
            self._available = False
            self._initialized = True
            return False

        encryption_key = key or os.getenv("TOKEN_ENCRYPTION_KEY")

        if not encryption_key:
            logger.warning(
                "encryption_disabled",
                reason="TOKEN_ENCRYPTION_KEY not set",
            )
            self._available = False
            self._initialized = True
            return False

        try:
            # Validate and create Fernet instance
            self._fernet = Fernet(encryption_key.encode())

            # Test encryption/decryption
            test_data = b"test"
            decrypted = self._fernet.decrypt(self._fernet.encrypt(test_data))
            assert decrypted == test_data

            self._available = True
            self._initialized = True
            logger.info("encryption_initialized")
            return True

        except Exception as e:
            logger.error(
                "encryption_init_failed",
                error=str(e),
                error_type=type(e).__name__,
            )
            self._available = False
            self._initialized = True
            return False

    @property
    def is_available(self) -> bool:
        """Check if encryption is available."""
        if not self._initialized:
            self.initialize()
        return self._available

    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt a string value.

        Args:
            plaintext: The string to encrypt

        Returns:
            Base64-encoded encrypted string

        Raises:
            EncryptionError: If encryption fails or is unavailable
        """
        if not self.is_available:
            raise EncryptionError("Encryption is not available")

        if self._fernet is None:
            raise EncryptionError("Encryption not initialized")

        try:
            encrypted = self._fernet.encrypt(plaintext.encode())
            return encrypted.decode()
        except Exception as e:
            logger.error("encrypt_failed", error=str(e))
            raise EncryptionError(f"Encryption failed: {e}")

    def decrypt(self, ciphertext: str) -> str:
        """
        Decrypt an encrypted string.

        Args:
            ciphertext: Base64-encoded encrypted string

        Returns:
            Decrypted plaintext string

        Raises:
            EncryptionError: If decryption fails or is unavailable
        """
        if not self.is_available:
            raise EncryptionError("Encryption is not available")

        if self._fernet is None:
            raise EncryptionError("Encryption not initialized")

        try:
            decrypted = self._fernet.decrypt(ciphertext.encode())
            return decrypted.decode()
        except InvalidToken:  # type: ignore[misc]
            logger.error("decrypt_invalid_token")
            raise EncryptionError("Invalid token - decryption failed")
        except Exception as e:
            logger.error("decrypt_failed", error=str(e))
            raise EncryptionError(f"Decryption failed: {e}")

    def encrypt_if_available(
        self, plaintext: str, require_encryption: bool = False
    ) -> tuple[str, bool]:
        """
        Encrypt if available, otherwise return original or raise error.

        Args:
            plaintext: The string to encrypt
            require_encryption: If True, raise error when encryption unavailable

        Returns:
            Tuple of (result_string, was_encrypted)

        Raises:
            EncryptionError: If require_encryption is True and encryption unavailable
        """
        if not self.is_available:
            if require_encryption:
                raise EncryptionError(
                    "Encryption is required but not available. "
                    "Set TOKEN_ENCRYPTION_KEY environment variable."
                )
            logger.warning(
                "encrypt_fallback_plaintext",
                message="Storing sensitive data in plaintext - encryption unavailable",
            )
            return plaintext, False

        try:
            encrypted = self.encrypt(plaintext)
            return encrypted, True
        except EncryptionError:
            if require_encryption:
                raise
            return plaintext, False

    def decrypt_if_encrypted(self, value: str) -> str:
        """
        Decrypt if the value appears to be encrypted.

        Fernet tokens start with 'gAAAAA' (base64 of timestamp + iv).

        Args:
            value: The string to potentially decrypt

        Returns:
            Decrypted string or original if not encrypted
        """
        if not self.is_available:
            return value

        # Fernet tokens are base64 and start with specific prefix
        if not value.startswith("gAAAAA"):
            return value

        try:
            return self.decrypt(value)
        except EncryptionError:
            # Not encrypted or wrong key, return original
            return value

    def rotate_key(self, old_key: str, new_key: str, ciphertext: str) -> str:
        """
        Re-encrypt data with a new key.

        Useful for key rotation procedures.

        Args:
            old_key: Current encryption key
            new_key: New encryption key
            ciphertext: Data encrypted with old key

        Returns:
            Data encrypted with new key
        """
        if not CRYPTOGRAPHY_AVAILABLE or Fernet is None:
            raise EncryptionError("cryptography package not installed")

        try:
            old_fernet = Fernet(old_key.encode())  # type: ignore[misc]
            new_fernet = Fernet(new_key.encode())  # type: ignore[misc]

            plaintext = old_fernet.decrypt(ciphertext.encode())
            return new_fernet.encrypt(plaintext).decode()
        except Exception as e:
            raise EncryptionError(f"Key rotation failed: {e}")


# Global singleton instance
_encryption_service: TokenEncryption | None = None


@lru_cache(maxsize=1)
def get_encryption_service() -> TokenEncryption:
    """Get the TokenEncryption singleton."""
    global _encryption_service
    if _encryption_service is None:
        _encryption_service = TokenEncryption()
        _encryption_service.initialize()
    return _encryption_service


def encrypt_token(token: str) -> str:
    """Convenience function to encrypt a token."""
    return get_encryption_service().encrypt(token)


def decrypt_token(encrypted: str) -> str:
    """Convenience function to decrypt a token."""
    return get_encryption_service().decrypt(encrypted)
