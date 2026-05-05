from __future__ import annotations

from app.utils.crypto import decrypt, encrypt


def test_roundtrip(tmp_env):
    blob = encrypt("ghp_secret_token_xyz")
    assert decrypt(blob) == "ghp_secret_token_xyz"


def test_decrypt_short_blob_raises(tmp_env):
    import pytest
    with pytest.raises(ValueError):
        decrypt(b"abc")
