"""
JWT utilities for MeshCore BBS web interface.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

import jwt
from datetime import datetime, timedelta
from typing import Optional
from dataclasses import dataclass


@dataclass
class TokenPayload:
    """JWT token payload."""

    sub: int  # Admin user ID
    username: str
    is_superadmin: bool
    exp: datetime
    iat: datetime
    type: str  # "access" or "refresh"


def create_access_token(
    admin_id: int,
    username: str,
    is_superadmin: bool,
    secret_key: str,
    expire_minutes: int = 15,
    algorithm: str = "HS256",
) -> str:
    """
    Create a JWT access token.

    Args:
        admin_id: Admin user ID
        username: Admin username
        is_superadmin: Superadmin flag
        secret_key: Secret key for signing
        expire_minutes: Token expiration in minutes
        algorithm: JWT algorithm

    Returns:
        Encoded JWT token
    """
    now = datetime.utcnow()
    expire = now + timedelta(minutes=expire_minutes)

    payload = {
        "sub": str(admin_id),  # JWT requires sub to be string
        "admin_id": admin_id,  # Keep numeric ID for convenience
        "username": username,
        "is_superadmin": is_superadmin,
        "exp": expire,
        "iat": now,
        "type": "access",
    }

    return jwt.encode(payload, secret_key, algorithm=algorithm)


def create_refresh_token(
    admin_id: int,
    secret_key: str,
    expire_days: int = 7,
    algorithm: str = "HS256",
) -> str:
    """
    Create a JWT refresh token.

    Args:
        admin_id: Admin user ID
        secret_key: Secret key for signing
        expire_days: Token expiration in days
        algorithm: JWT algorithm

    Returns:
        Encoded JWT token
    """
    now = datetime.utcnow()
    expire = now + timedelta(days=expire_days)

    payload = {
        "sub": str(admin_id),  # JWT requires sub to be string
        "admin_id": admin_id,  # Keep numeric ID for convenience
        "exp": expire,
        "iat": now,
        "type": "refresh",
    }

    return jwt.encode(payload, secret_key, algorithm=algorithm)


def decode_access_token(
    token: str,
    secret_key: str,
    algorithm: str = "HS256",
) -> Optional[TokenPayload]:
    """
    Decode and validate a JWT access token.

    Args:
        token: JWT token string
        secret_key: Secret key for verification
        algorithm: JWT algorithm

    Returns:
        TokenPayload if valid, None otherwise
    """
    try:
        payload = jwt.decode(token, secret_key, algorithms=[algorithm])

        # Verify token type
        if payload.get("type") != "access":
            return None

        # Get admin_id (use admin_id field if available, otherwise parse sub)
        admin_id = payload.get("admin_id") or int(payload["sub"])

        return TokenPayload(
            sub=admin_id,
            username=payload.get("username", ""),
            is_superadmin=payload.get("is_superadmin", False),
            exp=datetime.fromtimestamp(payload["exp"]),
            iat=datetime.fromtimestamp(payload["iat"]),
            type=payload["type"],
        )
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
    except Exception:
        return None


def decode_refresh_token(
    token: str,
    secret_key: str,
    algorithm: str = "HS256",
) -> Optional[int]:
    """
    Decode and validate a JWT refresh token.

    Args:
        token: JWT token string
        secret_key: Secret key for verification
        algorithm: JWT algorithm

    Returns:
        Admin ID if valid, None otherwise
    """
    try:
        payload = jwt.decode(token, secret_key, algorithms=[algorithm])

        # Verify token type
        if payload.get("type") != "refresh":
            return None

        # Get admin_id (use admin_id field if available, otherwise parse sub)
        return payload.get("admin_id") or int(payload["sub"])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
    except Exception:
        return None


def get_token_expiry(token: str, secret_key: str, algorithm: str = "HS256") -> Optional[datetime]:
    """
    Get the expiry time of a token without full validation.

    Args:
        token: JWT token string
        secret_key: Secret key
        algorithm: JWT algorithm

    Returns:
        Expiry datetime or None
    """
    try:
        # Decode without verification to get expiry
        payload = jwt.decode(
            token,
            secret_key,
            algorithms=[algorithm],
            options={"verify_exp": False},
        )
        return datetime.fromtimestamp(payload["exp"])
    except Exception:
        return None


def create_2fa_pending_token(
    admin_id: int,
    secret_key: str,
    expire_minutes: int = 5,
    algorithm: str = "HS256",
) -> str:
    """
    Create a temporary token for 2FA verification.

    This token is used after password verification but before 2FA.

    Args:
        admin_id: Admin user ID
        secret_key: Secret key for signing
        expire_minutes: Token expiration in minutes
        algorithm: JWT algorithm

    Returns:
        Encoded JWT token
    """
    now = datetime.utcnow()
    expire = now + timedelta(minutes=expire_minutes)

    payload = {
        "sub": str(admin_id),
        "admin_id": admin_id,
        "exp": expire,
        "iat": now,
        "type": "2fa_pending",
    }

    return jwt.encode(payload, secret_key, algorithm=algorithm)


def decode_2fa_pending_token(
    token: str,
    secret_key: str,
    algorithm: str = "HS256",
) -> Optional[int]:
    """
    Decode and validate a 2FA pending token.

    Args:
        token: JWT token string
        secret_key: Secret key for verification
        algorithm: JWT algorithm

    Returns:
        Admin ID if valid, None otherwise
    """
    try:
        payload = jwt.decode(token, secret_key, algorithms=[algorithm])

        # Verify token type
        if payload.get("type") != "2fa_pending":
            return None

        return payload.get("admin_id") or int(payload["sub"])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
    except Exception:
        return None
