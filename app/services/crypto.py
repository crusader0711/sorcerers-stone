"""AES-256-GCM field-level encryption — INV-1, INV-3 enforcing control.

Design: .kiro/specs/phase-1-architecture/design.md §5

Every Plaid access token (and any future sensitive field) is encrypted before
database write and decrypted only in memory when needed. The key is sourced
exclusively from /run/secrets/field_enc_key (Docker secret).

Encryption scheme:
  nonce (12 bytes) || ciphertext+tag (variable)
  AAD = record UUID bytes (binds ciphertext to a specific row — prevents row-swap attacks)
"""

from __future__ import annotations

import os
import uuid

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


NONCE_LEN = 12  # 96-bit nonce per NIST SP 800-38D


class FieldCipher:
    """Encrypt/decrypt sensitive fields using AES-256-GCM with per-record AAD.

    Args:
        key: Exactly 32 bytes (256 bits). Sourced from Settings.field_enc_key_bytes.

    Raises:
        ValueError: If key is not exactly 32 bytes.
        cryptography.exceptions.InvalidTag: On decryption if any of
            nonce/ciphertext/AAD has been tampered with.
    """

    def __init__(self, key: bytes) -> None:
        if len(key) != 32:
            raise ValueError(f"Key must be exactly 32 bytes, got {len(key)}")
        self._cipher = AESGCM(key)

    def encrypt(self, plaintext: bytes, record_id: uuid.UUID) -> bytes:
        """Encrypt plaintext, binding it to a specific record via AAD.

        Returns:
            bytes: nonce (12B) || ciphertext+tag
        """
        nonce = os.urandom(NONCE_LEN)
        aad = record_id.bytes
        ct = self._cipher.encrypt(nonce, plaintext, aad)
        return nonce + ct

    def decrypt(self, blob: bytes, record_id: uuid.UUID) -> bytes:
        """Decrypt a blob previously encrypted with encrypt().

        Args:
            blob: nonce (12B) || ciphertext+tag as stored in the database.
            record_id: The UUID of the record this blob belongs to (AAD).

        Returns:
            bytes: Original plaintext.

        Raises:
            cryptography.exceptions.InvalidTag: If blob or AAD has been tampered with.
            ValueError: If blob is too short to contain a valid nonce.
        """
        if len(blob) <= NONCE_LEN:
            raise ValueError(
                f"Blob too short ({len(blob)} bytes); must be > {NONCE_LEN}"
            )
        nonce = blob[:NONCE_LEN]
        ct = blob[NONCE_LEN:]
        aad = record_id.bytes
        return self._cipher.decrypt(nonce, ct, aad)
