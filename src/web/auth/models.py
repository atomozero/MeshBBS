"""
Admin user model for MeshCore BBS web interface.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

from datetime import datetime, timedelta
from typing import Optional, List
import json

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.orm import Session

from bbs.models.base import Base


class AdminUser(Base):
    """
    Admin user model for web interface authentication.

    Separate from BBS users - these are system administrators.
    """

    __tablename__ = "admin_users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    display_name = Column(String(100), nullable=True)
    email = Column(String(255), nullable=True)

    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    is_superadmin = Column(Boolean, default=False, nullable=False)

    # 2FA (TOTP)
    totp_secret = Column(String(64), nullable=True)
    totp_enabled = Column(Boolean, default=False, nullable=False)
    totp_backup_codes = Column(Text, nullable=True)  # JSON array of hashed codes

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)

    # Security
    failed_attempts = Column(Integer, default=0, nullable=False)
    locked_until = Column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<AdminUser(id={self.id}, username='{self.username}')>"

    @property
    def is_locked(self) -> bool:
        """Check if account is currently locked."""
        if self.locked_until is None:
            return False
        if datetime.utcnow() >= self.locked_until:
            # Lock expired, clear it
            self.locked_until = None
            self.failed_attempts = 0
            return False
        return True

    @property
    def lock_remaining_seconds(self) -> int:
        """Get remaining lock time in seconds."""
        if not self.is_locked:
            return 0
        return int((self.locked_until - datetime.utcnow()).total_seconds())

    def record_failed_attempt(self, max_attempts: int = 5, lockout_minutes: int = 15) -> None:
        """
        Record a failed login attempt.

        Args:
            max_attempts: Max attempts before lockout
            lockout_minutes: Lockout duration in minutes
        """
        self.failed_attempts += 1
        if self.failed_attempts >= max_attempts:
            self.locked_until = datetime.utcnow() + timedelta(minutes=lockout_minutes)

    def record_successful_login(self) -> None:
        """Record a successful login."""
        self.failed_attempts = 0
        self.locked_until = None
        self.last_login = datetime.utcnow()

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "username": self.username,
            "display_name": self.display_name or self.username,
            "email": self.email,
            "is_active": self.is_active,
            "is_superadmin": self.is_superadmin,
            "totp_enabled": self.totp_enabled,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_login": self.last_login.isoformat() if self.last_login else None,
        }

    @property
    def has_2fa(self) -> bool:
        """Check if 2FA is enabled for this user."""
        return self.totp_enabled and self.totp_secret is not None

    def get_backup_codes(self) -> List[str]:
        """Get list of hashed backup codes."""
        if not self.totp_backup_codes:
            return []
        try:
            return json.loads(self.totp_backup_codes)
        except (json.JSONDecodeError, TypeError):
            return []

    def set_backup_codes(self, codes: List[str]) -> None:
        """Set hashed backup codes."""
        self.totp_backup_codes = json.dumps(codes)

    def remove_backup_code(self, code_hash: str) -> None:
        """Remove a used backup code."""
        codes = self.get_backup_codes()
        if code_hash in codes:
            codes.remove(code_hash)
            self.set_backup_codes(codes)

    def enable_2fa(self, secret: str, backup_codes: List[str]) -> None:
        """Enable 2FA with secret and backup codes."""
        self.totp_secret = secret
        self.set_backup_codes(backup_codes)
        self.totp_enabled = True

    def disable_2fa(self) -> None:
        """Disable 2FA."""
        self.totp_secret = None
        self.totp_backup_codes = None
        self.totp_enabled = False


class AdminUserRepository:
    """Repository for AdminUser operations."""

    def __init__(self, session: Session):
        self.session = session

    def get_by_id(self, admin_id: int) -> Optional[AdminUser]:
        """Get admin by ID."""
        return self.session.query(AdminUser).filter(AdminUser.id == admin_id).first()

    def get_by_username(self, username: str) -> Optional[AdminUser]:
        """Get admin by username (case-insensitive)."""
        return (
            self.session.query(AdminUser)
            .filter(AdminUser.username.ilike(username))
            .first()
        )

    def get_all(self, include_inactive: bool = False) -> list[AdminUser]:
        """Get all admin users."""
        query = self.session.query(AdminUser)
        if not include_inactive:
            query = query.filter(AdminUser.is_active == True)
        return query.order_by(AdminUser.username).all()

    def create(
        self,
        username: str,
        password_hash: str,
        display_name: Optional[str] = None,
        email: Optional[str] = None,
        is_superadmin: bool = False,
    ) -> AdminUser:
        """
        Create a new admin user.

        Args:
            username: Unique username
            password_hash: Hashed password
            display_name: Display name
            email: Email address
            is_superadmin: Superadmin privileges

        Returns:
            Created AdminUser
        """
        admin = AdminUser(
            username=username.lower(),
            password_hash=password_hash,
            display_name=display_name,
            email=email,
            is_superadmin=is_superadmin,
        )
        self.session.add(admin)
        self.session.flush()
        return admin

    def update(self, admin: AdminUser, **kwargs) -> AdminUser:
        """Update admin user fields."""
        for key, value in kwargs.items():
            if hasattr(admin, key):
                setattr(admin, key, value)
        admin.updated_at = datetime.utcnow()
        return admin

    def delete(self, admin: AdminUser) -> None:
        """Delete an admin user."""
        self.session.delete(admin)

    def count(self) -> int:
        """Get total admin count."""
        return self.session.query(AdminUser).count()

    def count_superadmins(self) -> int:
        """Get superadmin count."""
        return (
            self.session.query(AdminUser)
            .filter(AdminUser.is_superadmin == True)
            .filter(AdminUser.is_active == True)
            .count()
        )
