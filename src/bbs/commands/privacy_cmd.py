"""
Privacy and GDPR commands for MeshCore BBS.

Commands: gdpr, cleanup, privacy.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

from typing import List

from sqlalchemy.orm import Session

from .base import BaseCommand, CommandContext, CommandResult, CommandRegistry
from bbs.privacy import RetentionManager, PrivacyInfo, check_sqlcipher_available


# Default retention values (can be overridden by config)
DEFAULT_PM_RETENTION_DAYS = 30
DEFAULT_LOG_RETENTION_DAYS = 90


@CommandRegistry.register
class GdprCommand(BaseCommand):
    """Show GDPR and privacy information."""

    name = "gdpr"
    description = "Informazioni privacy e GDPR"
    usage = "/gdpr"
    aliases = ["privacy"]
    admin_only = False

    def __init__(self, session: Session):
        self.session = session

    async def execute(
        self, ctx: CommandContext, args: List[str]
    ) -> CommandResult:
        """
        Execute the gdpr command.

        Shows privacy policy and data retention information.

        Args:
            ctx: Command context
            args: Not used

        Returns:
            GDPR information
        """
        # Check if SQLCipher is available
        encryption_enabled = check_sqlcipher_available()

        # Get retention settings (from config if available, otherwise defaults)
        try:
            from utils.config import get_config
            config = get_config()
            pm_retention = config.pm_retention_days
            log_retention = config.activity_log_retention_days
        except Exception:
            pm_retention = DEFAULT_PM_RETENTION_DAYS
            log_retention = DEFAULT_LOG_RETENTION_DAYS

        # Get GDPR info
        info = PrivacyInfo.get_gdpr_info(
            pm_retention_days=pm_retention,
            log_retention_days=log_retention,
            encryption_enabled=encryption_enabled,
        )

        return CommandResult.ok(info)


@CommandRegistry.register
class CleanupCommand(BaseCommand):
    """Run data retention cleanup (admin only)."""

    name = "cleanup"
    description = "Esegue pulizia dati (retention)"
    usage = "/cleanup [--dry-run]"
    aliases = ["retention"]
    admin_only = True

    def __init__(self, session: Session):
        self.session = session
        self.retention_manager = RetentionManager(session)

    async def execute(
        self, ctx: CommandContext, args: List[str]
    ) -> CommandResult:
        """
        Execute the cleanup command.

        Removes old PMs and activity logs based on retention policy.

        Args:
            ctx: Command context
            args: Optional [--dry-run] to preview without deleting

        Returns:
            Cleanup results
        """
        # Check for dry-run flag
        dry_run = "--dry-run" in args or "-n" in args

        # Get retention settings
        try:
            from utils.config import get_config
            config = get_config()
            pm_retention = config.pm_retention_days
            log_retention = config.activity_log_retention_days
        except Exception:
            pm_retention = DEFAULT_PM_RETENTION_DAYS
            log_retention = DEFAULT_LOG_RETENTION_DAYS

        if dry_run:
            # Preview mode - show what would be deleted
            stats = self.retention_manager.get_retention_stats(
                pm_retention_days=pm_retention,
                log_retention_days=log_retention,
            )

            lines = [
                "[BBS] Cleanup preview (dry-run):",
                f"  PM: {stats['expired_pms']}/{stats['total_pms']} da eliminare",
                f"  Log: {stats['expired_logs']}/{stats['total_logs']} da eliminare",
                f"  Retention PM: {pm_retention} giorni",
                f"  Retention Log: {log_retention} giorni",
                "Esegui /cleanup per eliminare",
            ]

            return CommandResult.ok("\n".join(lines))

        else:
            # Actually run cleanup
            pms_deleted, logs_deleted = self.retention_manager.run_cleanup(
                pm_retention_days=pm_retention,
                log_retention_days=log_retention,
            )

            if pms_deleted == 0 and logs_deleted == 0:
                return CommandResult.ok("[BBS] Nessun dato da eliminare")

            return CommandResult.ok(
                f"[BBS] Cleanup completato:\n"
                f"  PM eliminati: {pms_deleted}\n"
                f"  Log eliminati: {logs_deleted}"
            )


@CommandRegistry.register
class MyDataCommand(BaseCommand):
    """Show user's own data stored in the BBS."""

    name = "mydata"
    description = "Mostra i tuoi dati salvati"
    usage = "/mydata"
    aliases = ["myprivacy"]
    admin_only = False

    def __init__(self, session: Session):
        self.session = session

    async def execute(
        self, ctx: CommandContext, args: List[str]
    ) -> CommandResult:
        """
        Execute the mydata command.

        Shows what data is stored for the requesting user.

        Args:
            ctx: Command context
            args: Not used

        Returns:
            User's stored data summary
        """
        from bbs.models.user import User
        from bbs.models.message import Message
        from bbs.models.private_message import PrivateMessage
        from bbs.models.activity_log import ActivityLog

        # Get user
        user = self.session.query(User).filter_by(public_key=ctx.sender_key).first()

        if not user:
            return CommandResult.fail("[BBS] Utente non trovato")

        # Count user's data
        msg_count = (
            self.session.query(Message)
            .filter_by(sender_key=ctx.sender_key)
            .count()
        )

        pm_sent = (
            self.session.query(PrivateMessage)
            .filter_by(sender_key=ctx.sender_key)
            .count()
        )

        pm_received = (
            self.session.query(PrivateMessage)
            .filter_by(recipient_key=ctx.sender_key)
            .count()
        )

        log_entries = (
            self.session.query(ActivityLog)
            .filter_by(user_key=ctx.sender_key)
            .count()
        )

        # Build response
        lines = [
            "[BBS] I tuoi dati salvati:",
            f"  Nickname: {user.nickname or '(non impostato)'}",
            f"  Registrato: {user.first_seen.strftime('%d/%m/%Y')}",
            f"  Messaggi pubblici: {msg_count}",
            f"  PM inviati: {pm_sent}",
            f"  PM ricevuti: {pm_received}",
            f"  Log attivita: {log_entries}",
            "Usa /delpm per eliminare PM",
        ]

        return CommandResult.ok("\n".join(lines))
