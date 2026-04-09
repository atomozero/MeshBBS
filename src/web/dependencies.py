"""
FastAPI dependencies for MeshCore BBS web interface.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

from typing import Generator, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from bbs.models.base import get_session, get_session_factory
from web.config import get_web_config, WebConfig
from web.auth.jwt import decode_access_token, TokenPayload
from web.auth.models import AdminUser


# Security scheme for JWT
security = HTTPBearer(auto_error=False)


def get_db() -> Generator[Session, None, None]:
    """
    Dependency that provides a database session.

    Yields:
        Database session that auto-commits on success
    """
    with get_session() as session:
        yield session


def get_db_session() -> Generator[Session, None, None]:
    """
    Generator that provides a database session without context manager.
    Used by WebSocket where context manager doesn't work well.
    """
    factory = get_session_factory()
    session = factory()
    try:
        yield session
    finally:
        session.close()


def get_config() -> WebConfig:
    """Dependency that provides the web configuration."""
    return get_web_config()


async def get_current_admin(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> AdminUser:
    """
    Dependency that validates JWT and returns the current admin user.

    Args:
        credentials: Bearer token from Authorization header
        db: Database session

    Returns:
        AdminUser instance

    Raises:
        HTTPException: If authentication fails
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Non autenticato",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Decode token
    config = get_web_config()
    payload = decode_access_token(credentials.credentials, config.secret_key)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token non valido o scaduto",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Get admin from database
    admin = db.query(AdminUser).filter(AdminUser.id == payload.sub).first()

    if admin is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Utente non trovato",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not admin.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account disabilitato",
        )

    if admin.is_locked:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account bloccato temporaneamente",
        )

    return admin


async def get_current_superadmin(
    admin: AdminUser = Depends(get_current_admin),
) -> AdminUser:
    """
    Dependency that requires superadmin privileges.

    Args:
        admin: Current authenticated admin

    Returns:
        AdminUser instance (if superadmin)

    Raises:
        HTTPException: If not a superadmin
    """
    if not admin.is_superadmin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Richiesti privilegi di superadmin",
        )
    return admin


def get_optional_admin(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> Optional[AdminUser]:
    """
    Dependency that optionally validates JWT.

    Returns None if no token provided, raises exception only if token is invalid.

    Args:
        credentials: Bearer token from Authorization header
        db: Database session

    Returns:
        AdminUser instance or None
    """
    if credentials is None:
        return None

    config = get_web_config()
    payload = decode_access_token(credentials.credentials, config.secret_key)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token non valido o scaduto",
            headers={"WWW-Authenticate": "Bearer"},
        )

    admin = db.query(AdminUser).filter(AdminUser.id == payload.sub).first()

    if admin is None or not admin.is_active:
        return None

    return admin
