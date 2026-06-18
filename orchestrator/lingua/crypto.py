"""Symmetric encryption for secrets stored in the Credential Vault.

Secret values (GitHub PAT, model API key) are encrypted at rest with Fernet
(AES-128-CBC + HMAC) using a key from the `LINGUA_SECRET_KEY` environment
variable. Generate one with:

    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""

from __future__ import annotations

import os
from functools import lru_cache

from cryptography.fernet import Fernet


class SecretKeyMissing(RuntimeError):
    """Raised when LINGUA_SECRET_KEY is unset but a secret needs (de)encryption."""


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    key = os.getenv("LINGUA_SECRET_KEY")
    if not key:
        raise SecretKeyMissing(
            "LINGUA_SECRET_KEY is not set. Generate one with "
            "`python -c \"from cryptography.fernet import Fernet; "
            "print(Fernet.generate_key().decode())\"` and set it in the environment."
        )
    return Fernet(key.encode())


def encrypt(plaintext: str) -> str:
    """Encrypt a UTF-8 string, returning a URL-safe token."""
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt(token: str) -> str:
    """Decrypt a token produced by `encrypt`."""
    return _fernet().decrypt(token.encode()).decode()
