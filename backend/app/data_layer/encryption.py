"""
Field-level AES-256-GCM encryption for sensitive application data.
Master key loaded from environment — never hardcoded.
"""
import os
import base64
import hashlib
import logging
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from app.core.config import settings

logger = logging.getLogger(__name__)

# Derive a 256-bit key from the SECRET_KEY
def _derive_key() -> bytes:
    return hashlib.sha256(settings.SECRET_KEY.encode()).digest()


class FieldEncryptor:
    """AES-256-GCM field-level encryption for RESTRICTED data."""

    @classmethod
    def encrypt(cls, plaintext: str) -> str:
        """Encrypt a string value. Returns base64-encoded ciphertext."""
        if not plaintext:
            return ""
        try:
            key = _derive_key()
            aesgcm = AESGCM(key)
            nonce = os.urandom(12)  # 96-bit nonce
            ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
            # Package: nonce || ciphertext → base64
            return base64.b64encode(nonce + ciphertext).decode("ascii")
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            raise

    @classmethod
    def decrypt(cls, encrypted: str) -> str:
        """Decrypt a base64-encoded ciphertext. Returns plaintext."""
        if not encrypted:
            return ""
        try:
            key = _derive_key()
            aesgcm = AESGCM(key)
            raw = base64.b64decode(encrypted.encode("ascii"))
            nonce, ciphertext = raw[:12], raw[12:]
            return aesgcm.decrypt(nonce, ciphertext, None).decode("utf-8")
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise

    @classmethod
    def hash_token(cls, value: str) -> str:
        """
        One-way hash for citizen_ref tokens.
        Phone number → stable token (HMAC-SHA256).
        """
        key = _derive_key()
        import hmac as _hmac
        return _hmac.new(key, value.encode(), hashlib.sha256).hexdigest()[:32]
