"""
Privacy and GDPR compliance module for MeshCore BBS.

Handles:
- Data retention policies (automatic cleanup of old PMs and logs)
- SQLCipher database encryption support
- Ephemeral (non-saved) private messages

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

from datetime import datetime, timedelta
from typing import Optional, Tuple
import logging

from sqlalchemy.orm import Session
from sqlalchemy import and_

from bbs.models.private_message import PrivateMessage
from bbs.models.activity_log import ActivityLog

logger = logging.getLogger("meshbbs.privacy")


class RetentionManager:
    """
    Manages data retention policies for GDPR compliance.

    Automatically cleans up old private messages and activity logs
    based on configured retention periods.
    """

    def __init__(self, session: Session):
        self.session = session

    def cleanup_old_private_messages(self, retention_days: int) -> int:
        """
        Delete private messages older than retention period.

        Args:
            retention_days: Number of days to keep PMs (0 = keep forever)

        Returns:
            Number of messages deleted
        """
        if retention_days <= 0:
            return 0

        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)

        # Delete old messages
        deleted = (
            self.session.query(PrivateMessage)
            .filter(PrivateMessage.timestamp < cutoff_date)
            .delete(synchronize_session=False)
        )

        if deleted > 0:
            logger.info(f"Retention cleanup: deleted {deleted} PMs older than {retention_days} days")

        return deleted

    def cleanup_old_activity_logs(self, retention_days: int) -> int:
        """
        Delete activity logs older than retention period.

        Args:
            retention_days: Number of days to keep logs (0 = keep forever)

        Returns:
            Number of log entries deleted
        """
        if retention_days <= 0:
            return 0

        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)

        # Delete old logs
        deleted = (
            self.session.query(ActivityLog)
            .filter(ActivityLog.timestamp < cutoff_date)
            .delete(synchronize_session=False)
        )

        if deleted > 0:
            logger.info(f"Retention cleanup: deleted {deleted} log entries older than {retention_days} days")

        return deleted

    def run_cleanup(
        self,
        pm_retention_days: int = 30,
        log_retention_days: int = 90,
    ) -> Tuple[int, int]:
        """
        Run full retention cleanup.

        Args:
            pm_retention_days: Days to keep PMs
            log_retention_days: Days to keep logs

        Returns:
            Tuple of (pms_deleted, logs_deleted)
        """
        pms_deleted = self.cleanup_old_private_messages(pm_retention_days)
        logs_deleted = self.cleanup_old_activity_logs(log_retention_days)

        self.session.commit()

        return pms_deleted, logs_deleted

    def get_retention_stats(
        self,
        pm_retention_days: int = 30,
        log_retention_days: int = 90,
    ) -> dict:
        """
        Get statistics about data that would be affected by retention policy.

        Args:
            pm_retention_days: Days to keep PMs
            log_retention_days: Days to keep logs

        Returns:
            Dictionary with retention statistics
        """
        now = datetime.utcnow()

        # PM stats
        total_pms = self.session.query(PrivateMessage).count()
        if pm_retention_days > 0:
            pm_cutoff = now - timedelta(days=pm_retention_days)
            expired_pms = (
                self.session.query(PrivateMessage)
                .filter(PrivateMessage.timestamp < pm_cutoff)
                .count()
            )
        else:
            expired_pms = 0

        # Log stats
        total_logs = self.session.query(ActivityLog).count()
        if log_retention_days > 0:
            log_cutoff = now - timedelta(days=log_retention_days)
            expired_logs = (
                self.session.query(ActivityLog)
                .filter(ActivityLog.timestamp < log_cutoff)
                .count()
            )
        else:
            expired_logs = 0

        return {
            "total_pms": total_pms,
            "expired_pms": expired_pms,
            "pm_retention_days": pm_retention_days,
            "total_logs": total_logs,
            "expired_logs": expired_logs,
            "log_retention_days": log_retention_days,
        }


def check_sqlcipher_available() -> bool:
    """
    Check if SQLCipher is available for database encryption.

    Returns:
        True if SQLCipher is available, False otherwise
    """
    try:
        from sqlcipher3 import dbapi2
        return True
    except ImportError:
        try:
            from pysqlcipher3 import dbapi2
            return True
        except ImportError:
            return False


def get_sqlcipher_connection_string(db_path: str, key: Optional[str] = None) -> str:
    """
    Get connection string for SQLCipher encrypted database.

    Args:
        db_path: Path to database file
        key: Encryption key (None for unencrypted)

    Returns:
        SQLAlchemy connection string
    """
    if key and check_sqlcipher_available():
        # Use SQLCipher
        return f"sqlite+pysqlcipher://:{key}@/{db_path}"
    else:
        # Fall back to regular SQLite
        return f"sqlite:///{db_path}"


class PrivacyInfo:
    """Provides privacy-related information for users."""

    @staticmethod
    def get_privacy_notice() -> str:
        """Get privacy notice text for users."""
        return (
            "[BBS] Informativa Privacy:\n"
            "- I messaggi pubblici sono visibili a tutti\n"
            "- I PM sono salvati sul server\n"
            "- Usa /msg! per PM non salvati\n"
            "- I dati vengono eliminati periodicamente\n"
            "- Usa /gdpr per info complete"
        )

    @staticmethod
    def get_gdpr_info(
        pm_retention_days: int,
        log_retention_days: int,
        encryption_enabled: bool,
    ) -> str:
        """
        Get GDPR compliance information.

        Args:
            pm_retention_days: PM retention period
            log_retention_days: Log retention period
            encryption_enabled: Whether DB encryption is enabled

        Returns:
            GDPR information text
        """
        pm_policy = f"{pm_retention_days} giorni" if pm_retention_days > 0 else "indefinito"
        log_policy = f"{log_retention_days} giorni" if log_retention_days > 0 else "indefinito"
        encryption = "attiva" if encryption_enabled else "disattiva"

        return (
            "[BBS] GDPR Compliance:\n"
            f"  Retention PM: {pm_policy}\n"
            f"  Retention Log: {log_policy}\n"
            f"  Crittografia DB: {encryption}\n"
            "  Diritti: /delpm per eliminare PM\n"
            "  PM effimeri: /msg! (non salvati)"
        )
