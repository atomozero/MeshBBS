"""
Password hashing utilities for MeshCore BBS web interface.

Uses Argon2id for secure password hashing.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

import hashlib
import secrets
import base64
from typing import Tuple


# Argon2 parameters (if argon2-cffi is available)
try:
    from argon2 import PasswordHasher, Type
    from argon2.exceptions import VerifyMismatchError, InvalidHash

    _hasher = PasswordHasher(
        time_cost=2,
        memory_cost=65536,  # 64MB
        parallelism=1,
        hash_len=32,
        type=Type.ID,
    )
    _USE_ARGON2 = True
except ImportError:
    _USE_ARGON2 = False


def hash_password(password: str) -> str:
    """
    Hash a password using Argon2id (or PBKDF2 fallback).

    Args:
        password: Plain text password

    Returns:
        Hashed password string
    """
    if _USE_ARGON2:
        return _hasher.hash(password)
    else:
        # Fallback to PBKDF2-SHA256
        salt = secrets.token_bytes(32)
        key = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            iterations=100000,
            dklen=32,
        )
        # Format: pbkdf2:sha256:iterations$salt$hash
        salt_b64 = base64.b64encode(salt).decode("ascii")
        key_b64 = base64.b64encode(key).decode("ascii")
        return f"pbkdf2:sha256:100000${salt_b64}${key_b64}"


def verify_password(password: str, password_hash: str) -> bool:
    """
    Verify a password against its hash.

    Args:
        password: Plain text password to verify
        password_hash: Stored password hash

    Returns:
        True if password matches, False otherwise
    """
    try:
        if password_hash.startswith("pbkdf2:"):
            # PBKDF2 hash
            return _verify_pbkdf2(password, password_hash)
        elif _USE_ARGON2:
            # Argon2 hash
            _hasher.verify(password_hash, password)
            return True
        else:
            # Unknown format
            return False
    except (VerifyMismatchError if _USE_ARGON2 else Exception):
        return False
    except Exception:
        return False


def _verify_pbkdf2(password: str, password_hash: str) -> bool:
    """Verify a PBKDF2 password hash."""
    try:
        parts = password_hash.split("$")
        if len(parts) != 3:
            return False

        header, salt_b64, key_b64 = parts
        header_parts = header.split(":")
        if len(header_parts) != 3 or header_parts[0] != "pbkdf2":
            return False

        algorithm = header_parts[1]
        iterations = int(header_parts[2])

        salt = base64.b64decode(salt_b64)
        stored_key = base64.b64decode(key_b64)

        computed_key = hashlib.pbkdf2_hmac(
            algorithm,
            password.encode("utf-8"),
            salt,
            iterations=iterations,
            dklen=len(stored_key),
        )

        return secrets.compare_digest(computed_key, stored_key)
    except Exception:
        return False


def needs_rehash(password_hash: str) -> bool:
    """
    Check if a password hash needs to be rehashed.

    Returns True if using old algorithm or parameters.

    Args:
        password_hash: Current password hash

    Returns:
        True if rehash is recommended
    """
    if _USE_ARGON2:
        # Check if it's using Argon2
        if password_hash.startswith("pbkdf2:"):
            return True
        try:
            return _hasher.check_needs_rehash(password_hash)
        except Exception:
            return True
    return False


def generate_temp_password(length: int = 12) -> str:
    """
    Generate a temporary password.

    Args:
        length: Password length

    Returns:
        Random password string
    """
    alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*"
    return "".join(secrets.choice(alphabet) for _ in range(length))
