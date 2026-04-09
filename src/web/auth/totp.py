"""
TOTP Two-Factor Authentication for MeshCore BBS.

Implements RFC 6238 TOTP using the pyotp library.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

import base64
import hashlib
import hmac
import struct
import time
from typing import Optional, Tuple
from urllib.parse import quote


# TOTP configuration
TOTP_DIGITS = 6
TOTP_PERIOD = 30  # seconds
TOTP_ALGORITHM = "sha1"
TOTP_ISSUER = "MeshBBS"


def generate_secret(length: int = 32) -> str:
    """
    Generate a random base32-encoded secret for TOTP.

    Args:
        length: Number of bytes for the secret (default 32)

    Returns:
        Base32-encoded secret string
    """
    import secrets
    random_bytes = secrets.token_bytes(length)
    # Base32 encode and remove padding
    return base64.b32encode(random_bytes).decode("ascii").rstrip("=")


def get_totp_token(secret: str, time_offset: int = 0) -> str:
    """
    Generate a TOTP token for the given secret.

    Args:
        secret: Base32-encoded secret
        time_offset: Time offset in periods (for verification window)

    Returns:
        6-digit TOTP token
    """
    # Decode secret (add padding if needed)
    secret_padded = secret + "=" * ((8 - len(secret) % 8) % 8)
    key = base64.b32decode(secret_padded.upper())

    # Calculate time counter
    counter = (int(time.time()) // TOTP_PERIOD) + time_offset

    # Generate HMAC-SHA1
    counter_bytes = struct.pack(">Q", counter)
    hmac_hash = hmac.new(key, counter_bytes, hashlib.sha1).digest()

    # Dynamic truncation
    offset = hmac_hash[-1] & 0x0F
    code = struct.unpack(">I", hmac_hash[offset:offset + 4])[0]
    code = (code & 0x7FFFFFFF) % (10 ** TOTP_DIGITS)

    return str(code).zfill(TOTP_DIGITS)


def verify_totp(secret: str, token: str, window: int = 1) -> bool:
    """
    Verify a TOTP token.

    Args:
        secret: Base32-encoded secret
        token: 6-digit token to verify
        window: Number of periods to check before/after current

    Returns:
        True if token is valid
    """
    if not token or len(token) != TOTP_DIGITS:
        return False

    # Clean token
    token = token.strip()
    if not token.isdigit():
        return False

    # Check token against current and adjacent time periods
    for offset in range(-window, window + 1):
        expected = get_totp_token(secret, offset)
        if hmac.compare_digest(token, expected):
            return True

    return False


def get_provisioning_uri(
    secret: str,
    username: str,
    issuer: str = TOTP_ISSUER,
) -> str:
    """
    Generate a provisioning URI for authenticator apps.

    Args:
        secret: Base32-encoded secret
        username: User's account name
        issuer: Issuer name (e.g., app name)

    Returns:
        otpauth:// URI for QR code
    """
    label = f"{issuer}:{username}"
    params = {
        "secret": secret,
        "issuer": issuer,
        "algorithm": TOTP_ALGORITHM.upper(),
        "digits": str(TOTP_DIGITS),
        "period": str(TOTP_PERIOD),
    }

    param_str = "&".join(f"{k}={quote(str(v))}" for k, v in params.items())
    return f"otpauth://totp/{quote(label)}?{param_str}"


def generate_backup_codes(count: int = 10, length: int = 8) -> list[str]:
    """
    Generate backup codes for account recovery.

    Args:
        count: Number of codes to generate
        length: Length of each code

    Returns:
        List of backup codes
    """
    import secrets
    codes = []
    for _ in range(count):
        # Generate alphanumeric code
        code = secrets.token_hex(length // 2).upper()
        # Format as XXXX-XXXX
        formatted = f"{code[:4]}-{code[4:]}"
        codes.append(formatted)
    return codes


def hash_backup_code(code: str) -> str:
    """
    Hash a backup code for storage.

    Args:
        code: Backup code

    Returns:
        SHA256 hash of the code
    """
    # Normalize: uppercase, remove dashes/spaces
    normalized = code.upper().replace("-", "").replace(" ", "")
    return hashlib.sha256(normalized.encode()).hexdigest()


def verify_backup_code(code: str, hashed_codes: list[str]) -> Optional[str]:
    """
    Verify a backup code against stored hashes.

    Args:
        code: Backup code to verify
        hashed_codes: List of hashed backup codes

    Returns:
        The matching hash if valid, None otherwise
    """
    code_hash = hash_backup_code(code)
    for stored_hash in hashed_codes:
        if hmac.compare_digest(code_hash, stored_hash):
            return stored_hash
    return None


class TOTPManager:
    """
    Manages TOTP 2FA for a user.

    Provides methods for setup, verification, and backup codes.
    """

    def __init__(
        self,
        secret: Optional[str] = None,
        backup_codes: Optional[list[str]] = None,
    ):
        """
        Initialize TOTP manager.

        Args:
            secret: Existing TOTP secret (None to generate)
            backup_codes: List of hashed backup codes
        """
        self.secret = secret
        self.backup_codes = backup_codes or []

    def setup(self, username: str) -> Tuple[str, str, list[str]]:
        """
        Setup TOTP for a user.

        Args:
            username: User's account name

        Returns:
            Tuple of (secret, provisioning_uri, backup_codes)
        """
        self.secret = generate_secret()
        uri = get_provisioning_uri(self.secret, username)
        codes = generate_backup_codes()
        self.backup_codes = [hash_backup_code(c) for c in codes]

        return self.secret, uri, codes

    def verify(self, token: str) -> bool:
        """
        Verify a TOTP token.

        Args:
            token: 6-digit TOTP token

        Returns:
            True if valid
        """
        if not self.secret:
            return False
        return verify_totp(self.secret, token)

    def verify_backup(self, code: str) -> bool:
        """
        Verify a backup code.

        Args:
            code: Backup code (format: XXXX-XXXX)

        Returns:
            True if valid (and removes the used code)
        """
        matching_hash = verify_backup_code(code, self.backup_codes)
        if matching_hash:
            self.backup_codes.remove(matching_hash)
            return True
        return False

    def regenerate_backup_codes(self) -> list[str]:
        """
        Regenerate all backup codes.

        Returns:
            List of new backup codes
        """
        codes = generate_backup_codes()
        self.backup_codes = [hash_backup_code(c) for c in codes]
        return codes

    @property
    def is_enabled(self) -> bool:
        """Check if 2FA is enabled."""
        return self.secret is not None

    @property
    def backup_codes_remaining(self) -> int:
        """Get number of remaining backup codes."""
        return len(self.backup_codes)
