"""Property-based tests for the FieldCipher (AES-256-GCM).

Tests crypto invariants:
  1. Encrypt → decrypt is a lossless round-trip for arbitrary bytes
  2. Different record_ids produce different ciphertext (AAD binding)
  3. Tampering with any byte of (nonce || ciphertext || tag) raises InvalidTag
  4. Using wrong record_id (AAD mismatch) raises InvalidTag
  5. Key must be exactly 32 bytes

Ref: .kiro/specs/phase-1-architecture/design.md §5
"""

import os
import uuid

import pytest
from cryptography.exceptions import InvalidTag
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.services.crypto import FieldCipher, NONCE_LEN


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def cipher() -> FieldCipher:
    """A FieldCipher with a random 32-byte key."""
    return FieldCipher(os.urandom(32))


@pytest.fixture
def key() -> bytes:
    return os.urandom(32)


# ── Property: Round-trip ──────────────────────────────────────────────────────

@given(plaintext=st.binary(min_size=0, max_size=65536))
@settings(max_examples=200)
def test_encrypt_decrypt_roundtrip(plaintext: bytes) -> None:
    """Arbitrary plaintext survives encrypt → decrypt unchanged."""
    key = os.urandom(32)
    cipher = FieldCipher(key)
    record_id = uuid.uuid4()

    blob = cipher.encrypt(plaintext, record_id)
    recovered = cipher.decrypt(blob, record_id)

    assert recovered == plaintext


# ── Property: AAD binding (different record_id = different ciphertext) ────────

@given(plaintext=st.binary(min_size=1, max_size=1024))
@settings(max_examples=100)
def test_different_record_ids_produce_different_ciphertext(plaintext: bytes) -> None:
    """Same plaintext encrypted under different record IDs produces different blobs."""
    key = os.urandom(32)
    cipher = FieldCipher(key)
    id1 = uuid.uuid4()
    id2 = uuid.uuid4()
    assume(id1 != id2)

    blob1 = cipher.encrypt(plaintext, id1)
    blob2 = cipher.encrypt(plaintext, id2)

    # Blobs differ (nonce alone would guarantee this, but AAD adds semantic binding)
    assert blob1 != blob2


# ── Property: Tamper detection ────────────────────────────────────────────────

@given(
    plaintext=st.binary(min_size=1, max_size=1024),
    flip_offset=st.integers(min_value=0, max_value=1023),
)
@settings(max_examples=200)
def test_tamper_detection_flipped_byte(plaintext: bytes, flip_offset: int) -> None:
    """Flipping any byte in the encrypted blob raises InvalidTag on decrypt."""
    key = os.urandom(32)
    cipher = FieldCipher(key)
    record_id = uuid.uuid4()

    blob = cipher.encrypt(plaintext, record_id)

    # Constrain flip_offset to blob length
    idx = flip_offset % len(blob)
    tampered = bytearray(blob)
    tampered[idx] ^= 0x01  # flip one bit
    tampered = bytes(tampered)

    # Tampered blob must fail decryption
    with pytest.raises((InvalidTag, ValueError)):
        cipher.decrypt(tampered, record_id)


# ── Property: Wrong AAD raises InvalidTag ─────────────────────────────────────

@given(plaintext=st.binary(min_size=1, max_size=1024))
@settings(max_examples=100)
def test_wrong_record_id_raises_invalid_tag(plaintext: bytes) -> None:
    """Decrypting with a different record_id (wrong AAD) must fail."""
    key = os.urandom(32)
    cipher = FieldCipher(key)

    real_id = uuid.uuid4()
    wrong_id = uuid.uuid4()
    assume(real_id != wrong_id)

    blob = cipher.encrypt(plaintext, real_id)

    with pytest.raises(InvalidTag):
        cipher.decrypt(blob, wrong_id)


# ── Unit: Key validation ──────────────────────────────────────────────────────

@pytest.mark.parametrize("bad_key_len", [0, 15, 16, 24, 31, 33, 64])
def test_invalid_key_lengths_rejected(bad_key_len: int) -> None:
    """Only 32-byte keys are accepted."""
    with pytest.raises(ValueError, match="32 bytes"):
        FieldCipher(os.urandom(bad_key_len))


# ── Unit: Empty blob ──────────────────────────────────────────────────────────

def test_decrypt_empty_blob_raises(cipher: FieldCipher) -> None:
    """Blob shorter than nonce length must raise ValueError."""
    record_id = uuid.uuid4()
    with pytest.raises(ValueError, match="too short"):
        cipher.decrypt(b"", record_id)

    with pytest.raises(ValueError, match="too short"):
        cipher.decrypt(os.urandom(NONCE_LEN), record_id)


# ── Unit: Ciphertext does not contain plaintext ───────────────────────────────

@given(plaintext=st.binary(min_size=16, max_size=1024))
@settings(max_examples=100)
def test_plaintext_not_visible_in_ciphertext(plaintext: bytes) -> None:
    """Encrypted output must not contain the plaintext verbatim."""
    key = os.urandom(32)
    cipher = FieldCipher(key)
    record_id = uuid.uuid4()

    blob = cipher.encrypt(plaintext, record_id)

    assert plaintext not in blob
