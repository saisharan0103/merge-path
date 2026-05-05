"""AES-GCM encryption for storing the GitHub PAT at rest.

Key is read from `ENCRYPTION_KEY` env (base64-encoded 32 bytes). If absent, we
auto-generate a key on first use and persist it to `data/.encryption_key` so
local dev still works without setup. For production deployments, the user
should set a stable key in `.env`.
"""

from __future__ import annotations

import base64
import os
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config import settings

_KEY_FALLBACK_PATH = Path("./data/.encryption_key")


def _load_key() -> bytes:
    if settings.encryption_key:
        try:
            raw = base64.b64decode(settings.encryption_key)
            if len(raw) == 32:
                return raw
        except Exception:
            pass
    _KEY_FALLBACK_PATH.parent.mkdir(parents=True, exist_ok=True)
    if _KEY_FALLBACK_PATH.exists():
        raw = base64.b64decode(_KEY_FALLBACK_PATH.read_text().strip())
        if len(raw) == 32:
            return raw
    raw = AESGCM.generate_key(bit_length=256)
    _KEY_FALLBACK_PATH.write_text(base64.b64encode(raw).decode())
    return raw


_KEY: bytes | None = None


def _key() -> bytes:
    global _KEY
    if _KEY is None:
        _KEY = _load_key()
    return _KEY


def encrypt(plaintext: str) -> bytes:
    """AES-GCM encrypt; returns nonce(12) + ciphertext."""
    aes = AESGCM(_key())
    nonce = os.urandom(12)
    ct = aes.encrypt(nonce, plaintext.encode("utf-8"), None)
    return nonce + ct


def decrypt(blob: bytes) -> str:
    if not blob or len(blob) <= 12:
        raise ValueError("ciphertext too short")
    aes = AESGCM(_key())
    nonce, ct = blob[:12], blob[12:]
    return aes.decrypt(nonce, ct, None).decode("utf-8")
