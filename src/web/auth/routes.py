"""
Authentication routes for MeshCore BBS web interface.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Response, Cookie
from fastapi.security import HTTPBasicCredentials
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from web.dependencies import get_db, get_config, get_current_admin
from web.config import WebConfig
from web.auth.models import AdminUser, AdminUserRepository
from web.auth.password import hash_password, verify_password
from web.auth.jwt import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    create_2fa_pending_token,
    decode_2fa_pending_token,
)
from web.auth.totp import (
    generate_secret,
    verify_totp,
    get_provisioning_uri,
    generate_backup_codes,
    hash_backup_code,
    verify_backup_code,
)


router = APIRouter(prefix="/auth", tags=["Authentication"])


# Request/Response schemas
class LoginRequest(BaseModel):
    """Login request schema."""

    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6, max_length=128)


class TokenResponse(BaseModel):
    """Token response schema."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int


class AdminResponse(BaseModel):
    """Admin user response schema."""

    id: int
    username: str
    display_name: str
    email: Optional[str]
    is_active: bool
    is_superadmin: bool
    created_at: Optional[str]
    last_login: Optional[str]


class CreateAdminRequest(BaseModel):
    """Create admin request schema."""

    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-zA-Z][a-zA-Z0-9_]*$")
    password: str = Field(..., min_length=8, max_length=128)
    display_name: Optional[str] = Field(None, max_length=100)
    email: Optional[str] = Field(None, max_length=255)
    is_superadmin: bool = False


class UpdateAdminRequest(BaseModel):
    """Update admin request schema."""

    display_name: Optional[str] = Field(None, max_length=100)
    email: Optional[str] = Field(None, max_length=255)
    is_active: Optional[bool] = None
    is_superadmin: Optional[bool] = None


class ChangePasswordRequest(BaseModel):
    """Change password request schema."""

    current_password: str = Field(..., min_length=6)
    new_password: str = Field(..., min_length=8, max_length=128)


class TwoFactorLoginRequest(BaseModel):
    """2FA verification during login."""

    pending_token: str
    totp_code: str = Field(..., min_length=6, max_length=10)


class TwoFactorPendingResponse(BaseModel):
    """Response when 2FA is required."""

    requires_2fa: bool = True
    pending_token: str
    message: str = "Autenticazione a due fattori richiesta"


class Setup2FAResponse(BaseModel):
    """Response for 2FA setup."""

    secret: str
    provisioning_uri: str
    backup_codes: list[str]
    qr_data: str  # For QR code generation


class Verify2FARequest(BaseModel):
    """Request to verify TOTP code."""

    totp_code: str = Field(..., min_length=6, max_length=6)


class Disable2FARequest(BaseModel):
    """Request to disable 2FA."""

    password: str
    totp_code: Optional[str] = None  # Or backup code


class BackupCodesResponse(BaseModel):
    """Response with backup codes."""

    backup_codes: list[str]
    remaining: int


@router.post("/login")
async def login(
    request: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
    config: WebConfig = Depends(get_config),
):
    """
    Authenticate and get access token.

    If 2FA is enabled, returns a pending token that must be verified with /auth/2fa/verify.
    Otherwise returns JWT access token and sets refresh token as httpOnly cookie.
    """
    repo = AdminUserRepository(db)
    admin = repo.get_by_username(request.username)

    # Check if user exists
    if admin is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenziali non valide",
        )

    # Check if locked
    if admin.is_locked:
        remaining = admin.lock_remaining_seconds
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=f"Account bloccato. Riprova tra {remaining // 60} minuti",
        )

    # Check if active
    if not admin.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account disabilitato",
        )

    # Verify password
    if not verify_password(request.password, admin.password_hash):
        admin.record_failed_attempt(
            max_attempts=config.auth_max_attempts,
            lockout_minutes=config.auth_lockout_minutes,
        )
        db.commit()

        if admin.is_locked:
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail=f"Troppi tentativi. Account bloccato per {config.auth_lockout_minutes} minuti",
            )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenziali non valide",
        )

    # Check if 2FA is enabled
    if admin.has_2fa:
        # Create pending token for 2FA verification
        pending_token = create_2fa_pending_token(
            admin_id=admin.id,
            secret_key=config.secret_key,
            expire_minutes=5,
        )
        return TwoFactorPendingResponse(
            requires_2fa=True,
            pending_token=pending_token,
        )

    # No 2FA - complete login
    return _complete_login(admin, response, config, db)


def _complete_login(
    admin: AdminUser,
    response: Response,
    config: WebConfig,
    db: Session,
) -> TokenResponse:
    """Complete the login process after all verification."""
    # Record successful login
    admin.record_successful_login()
    db.commit()

    # Create tokens
    access_token = create_access_token(
        admin_id=admin.id,
        username=admin.username,
        is_superadmin=admin.is_superadmin,
        secret_key=config.secret_key,
        expire_minutes=config.jwt_access_token_expire_minutes,
    )

    refresh_token = create_refresh_token(
        admin_id=admin.id,
        secret_key=config.secret_key,
        expire_days=config.jwt_refresh_token_expire_days,
    )

    # Set refresh token as httpOnly cookie
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=not config.debug,  # Secure in production
        samesite="lax",
        max_age=config.jwt_refresh_token_expire_days * 24 * 60 * 60,
        path="/api/v1/auth",
    )

    return TokenResponse(
        access_token=access_token,
        expires_in=config.jwt_access_token_expire_minutes * 60,
    )


@router.post("/2fa/verify", response_model=TokenResponse)
async def verify_2fa_login(
    request: TwoFactorLoginRequest,
    response: Response,
    db: Session = Depends(get_db),
    config: WebConfig = Depends(get_config),
):
    """
    Verify 2FA code and complete login.

    Accepts either a TOTP code or a backup code.
    """
    # Decode pending token
    admin_id = decode_2fa_pending_token(request.pending_token, config.secret_key)
    if admin_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token 2FA scaduto o non valido",
        )

    # Get admin
    repo = AdminUserRepository(db)
    admin = repo.get_by_id(admin_id)

    if admin is None or not admin.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Utente non trovato",
        )

    # Verify TOTP code
    code = request.totp_code.strip()

    # Try TOTP first
    if len(code) == 6 and code.isdigit():
        if verify_totp(admin.totp_secret, code):
            return _complete_login(admin, response, config, db)

    # Try backup code (format: XXXX-XXXX)
    backup_codes = admin.get_backup_codes()
    matching_hash = verify_backup_code(code, backup_codes)
    if matching_hash:
        admin.remove_backup_code(matching_hash)
        db.commit()
        return _complete_login(admin, response, config, db)

    # Invalid code
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Codice 2FA non valido",
    )


@router.post("/logout")
async def logout(response: Response):
    """
    Logout and clear refresh token cookie.
    """
    response.delete_cookie(
        key="refresh_token",
        path="/api/v1/auth",
    )
    return {"message": "Logout effettuato"}


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    response: Response,
    refresh_token: Optional[str] = Cookie(None),
    db: Session = Depends(get_db),
    config: WebConfig = Depends(get_config),
):
    """
    Refresh access token using refresh token from cookie.
    """
    if refresh_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token mancante",
        )

    # Decode refresh token
    admin_id = decode_refresh_token(refresh_token, config.secret_key)

    if admin_id is None:
        response.delete_cookie(key="refresh_token", path="/api/v1/auth")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token non valido o scaduto",
        )

    # Get admin
    repo = AdminUserRepository(db)
    admin = repo.get_by_id(admin_id)

    if admin is None or not admin.is_active:
        response.delete_cookie(key="refresh_token", path="/api/v1/auth")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Utente non trovato o disabilitato",
        )

    # Create new access token
    access_token = create_access_token(
        admin_id=admin.id,
        username=admin.username,
        is_superadmin=admin.is_superadmin,
        secret_key=config.secret_key,
        expire_minutes=config.jwt_access_token_expire_minutes,
    )

    return TokenResponse(
        access_token=access_token,
        expires_in=config.jwt_access_token_expire_minutes * 60,
    )


@router.get("/me", response_model=AdminResponse)
async def get_current_user(admin: AdminUser = Depends(get_current_admin)):
    """
    Get current authenticated admin user info.
    """
    return AdminResponse(
        id=admin.id,
        username=admin.username,
        display_name=admin.display_name or admin.username,
        email=admin.email,
        is_active=admin.is_active,
        is_superadmin=admin.is_superadmin,
        created_at=admin.created_at.isoformat() if admin.created_at else None,
        last_login=admin.last_login.isoformat() if admin.last_login else None,
    )


@router.post("/change-password")
async def change_password(
    request: ChangePasswordRequest,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Change current admin's password.
    """
    # Verify current password
    if not verify_password(request.current_password, admin.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password attuale non corretta",
        )

    # Update password
    admin.password_hash = hash_password(request.new_password)
    admin.updated_at = datetime.utcnow()
    db.commit()

    return {"message": "Password modificata con successo"}


# Admin management endpoints (superadmin only)
@router.get("/admins", response_model=list[AdminResponse])
async def list_admins(
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    List all admin users.

    Requires superadmin for full list, regular admins see limited info.
    """
    repo = AdminUserRepository(db)
    admins = repo.get_all(include_inactive=admin.is_superadmin)

    return [
        AdminResponse(
            id=a.id,
            username=a.username,
            display_name=a.display_name or a.username,
            email=a.email if admin.is_superadmin else None,
            is_active=a.is_active,
            is_superadmin=a.is_superadmin,
            created_at=a.created_at.isoformat() if a.created_at else None,
            last_login=a.last_login.isoformat() if a.last_login else None,
        )
        for a in admins
    ]


@router.post("/admins", response_model=AdminResponse, status_code=status.HTTP_201_CREATED)
async def create_admin(
    request: CreateAdminRequest,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Create a new admin user.

    Requires superadmin privileges.
    """
    if not admin.is_superadmin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Richiesti privilegi di superadmin",
        )

    repo = AdminUserRepository(db)

    # Check if username exists
    existing = repo.get_by_username(request.username)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username già esistente",
        )

    # Create admin
    new_admin = repo.create(
        username=request.username,
        password_hash=hash_password(request.password),
        display_name=request.display_name,
        email=request.email,
        is_superadmin=request.is_superadmin,
    )
    db.commit()

    return AdminResponse(
        id=new_admin.id,
        username=new_admin.username,
        display_name=new_admin.display_name or new_admin.username,
        email=new_admin.email,
        is_active=new_admin.is_active,
        is_superadmin=new_admin.is_superadmin,
        created_at=new_admin.created_at.isoformat() if new_admin.created_at else None,
        last_login=None,
    )


@router.patch("/admins/{admin_id}", response_model=AdminResponse)
async def update_admin(
    admin_id: int,
    request: UpdateAdminRequest,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Update an admin user.

    Requires superadmin privileges.
    """
    if not admin.is_superadmin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Richiesti privilegi di superadmin",
        )

    repo = AdminUserRepository(db)
    target = repo.get_by_id(admin_id)

    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Admin non trovato",
        )

    # Prevent removing last superadmin
    if (
        request.is_superadmin is False
        and target.is_superadmin
        and repo.count_superadmins() <= 1
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Impossibile rimuovere l'ultimo superadmin",
        )

    # Update fields
    update_data = request.model_dump(exclude_unset=True)
    repo.update(target, **update_data)
    db.commit()

    return AdminResponse(
        id=target.id,
        username=target.username,
        display_name=target.display_name or target.username,
        email=target.email,
        is_active=target.is_active,
        is_superadmin=target.is_superadmin,
        created_at=target.created_at.isoformat() if target.created_at else None,
        last_login=target.last_login.isoformat() if target.last_login else None,
    )


@router.delete("/admins/{admin_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_admin(
    admin_id: int,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Delete an admin user.

    Requires superadmin privileges. Cannot delete yourself or last superadmin.
    """
    if not admin.is_superadmin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Richiesti privilegi di superadmin",
        )

    if admin_id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Non puoi eliminare te stesso",
        )

    repo = AdminUserRepository(db)
    target = repo.get_by_id(admin_id)

    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Admin non trovato",
        )

    # Prevent removing last superadmin
    if target.is_superadmin and repo.count_superadmins() <= 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Impossibile eliminare l'ultimo superadmin",
        )

    repo.delete(target)
    db.commit()


# 2FA Management Endpoints
@router.post("/2fa/setup", response_model=Setup2FAResponse)
async def setup_2fa(
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Setup 2FA for the current admin.

    Returns the secret, provisioning URI for QR code, and backup codes.
    Store the backup codes securely - they cannot be retrieved again!
    """
    if admin.has_2fa:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="2FA già abilitato. Disabilitalo prima di riconfigurare.",
        )

    # Generate secret and backup codes
    secret = generate_secret()
    uri = get_provisioning_uri(secret, admin.username)
    backup_codes = generate_backup_codes()

    # Store hashed backup codes temporarily (not enabled yet)
    hashed_codes = [hash_backup_code(c) for c in backup_codes]

    # Store secret but don't enable yet
    admin.totp_secret = secret
    admin.set_backup_codes(hashed_codes)
    # Note: totp_enabled remains False until verified
    db.commit()

    return Setup2FAResponse(
        secret=secret,
        provisioning_uri=uri,
        backup_codes=backup_codes,
        qr_data=uri,  # Same as provisioning_uri for QR generation
    )


@router.post("/2fa/enable")
async def enable_2fa(
    request: Verify2FARequest,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Enable 2FA after setup.

    Requires a valid TOTP code to confirm the authenticator app is configured.
    """
    if admin.has_2fa:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="2FA già abilitato",
        )

    if not admin.totp_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Esegui prima /2fa/setup",
        )

    # Verify the TOTP code
    if not verify_totp(admin.totp_secret, request.totp_code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Codice TOTP non valido. Verifica la configurazione dell'app.",
        )

    # Enable 2FA
    admin.totp_enabled = True
    db.commit()

    return {"message": "2FA abilitato con successo"}


@router.post("/2fa/disable")
async def disable_2fa(
    request: Disable2FARequest,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Disable 2FA for the current admin.

    Requires current password and either a TOTP code or backup code.
    """
    if not admin.has_2fa:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="2FA non abilitato",
        )

    # Verify password
    if not verify_password(request.password, admin.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password non corretta",
        )

    # Verify TOTP or backup code if provided
    if request.totp_code:
        code = request.totp_code.strip()

        # Try TOTP
        if len(code) == 6 and code.isdigit():
            if not verify_totp(admin.totp_secret, code):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Codice TOTP non valido",
                )
        else:
            # Try backup code
            backup_codes = admin.get_backup_codes()
            if not verify_backup_code(code, backup_codes):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Codice non valido",
                )

    # Disable 2FA
    admin.disable_2fa()
    db.commit()

    return {"message": "2FA disabilitato"}


@router.get("/2fa/status")
async def get_2fa_status(
    admin: AdminUser = Depends(get_current_admin),
):
    """
    Get 2FA status for the current admin.
    """
    return {
        "enabled": admin.has_2fa,
        "backup_codes_remaining": len(admin.get_backup_codes()) if admin.has_2fa else 0,
    }


@router.post("/2fa/backup-codes", response_model=BackupCodesResponse)
async def regenerate_backup_codes(
    request: Verify2FARequest,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Regenerate backup codes.

    Requires a valid TOTP code. All existing backup codes are invalidated.
    """
    if not admin.has_2fa:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="2FA non abilitato",
        )

    # Verify TOTP code
    if not verify_totp(admin.totp_secret, request.totp_code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Codice TOTP non valido",
        )

    # Generate new backup codes
    backup_codes = generate_backup_codes()
    hashed_codes = [hash_backup_code(c) for c in backup_codes]
    admin.set_backup_codes(hashed_codes)
    db.commit()

    return BackupCodesResponse(
        backup_codes=backup_codes,
        remaining=len(backup_codes),
    )
