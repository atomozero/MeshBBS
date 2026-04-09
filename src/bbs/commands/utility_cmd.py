"""
Utility commands for MeshCore BBS.

Commands: delpm, clear, stats, info, whois.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

from datetime import datetime, timedelta
from typing import List

from sqlalchemy.orm import Session
from sqlalchemy import func

from .base import BaseCommand, CommandContext, CommandResult, CommandRegistry
from bbs.repositories.private_message_repository import PrivateMessageRepository
from bbs.repositories.user_repository import UserRepository
from bbs.repositories.area_repository import AreaRepository
from bbs.models.user import User
from bbs.models.message import Message
from bbs.models.private_message import PrivateMessage
from bbs.models.area import Area


@CommandRegistry.register
class DelPmCommand(BaseCommand):
    """Delete a private message from inbox."""

    name = "delpm"
    description = "Elimina un messaggio privato"
    usage = "/delpm <id>"
    aliases = ["deletepm", "rmpm"]
    admin_only = False

    def __init__(self, session: Session):
        self.session = session
        self.pm_repo = PrivateMessageRepository(session)

    async def execute(
        self, ctx: CommandContext, args: List[str]
    ) -> CommandResult:
        """
        Execute the delpm command.

        Args:
            ctx: Command context
            args: [message_id]

        Returns:
            Result of the deletion
        """
        if not args:
            return CommandResult.fail(
                "[BBS] Uso: /delpm <id>\n"
                "Elimina un messaggio dalla tua inbox"
            )

        # Parse message ID
        try:
            msg_id = int(args[0].lstrip("#"))
        except ValueError:
            return CommandResult.fail("[BBS] ID non valido")

        # Get message
        message = self.pm_repo.get_message_for_user(msg_id, ctx.sender_key)

        if not message:
            return CommandResult.fail(
                f"[BBS] Messaggio #{msg_id} non trovato"
            )

        # Check if user is sender or recipient
        is_sender = message.sender_key == ctx.sender_key
        is_recipient = message.recipient_key == ctx.sender_key

        if not is_sender and not is_recipient:
            return CommandResult.fail(
                f"[BBS] Messaggio #{msg_id} non trovato"
            )

        # Delete message
        self.session.delete(message)
        self.session.commit()

        return CommandResult.ok(f"[BBS] Messaggio #{msg_id} eliminato")


@CommandRegistry.register
class ClearInboxCommand(BaseCommand):
    """Mark all inbox messages as read."""

    name = "clear"
    description = "Marca tutti i PM come letti"
    usage = "/clear"
    aliases = ["readall", "markread"]
    admin_only = False

    def __init__(self, session: Session):
        self.session = session
        self.pm_repo = PrivateMessageRepository(session)

    async def execute(
        self, ctx: CommandContext, args: List[str]
    ) -> CommandResult:
        """
        Execute the clear command.

        Args:
            ctx: Command context
            args: Not used

        Returns:
            Result of the operation
        """
        # Get all unread messages
        unread_messages = (
            self.session.query(PrivateMessage)
            .filter(PrivateMessage.recipient_key == ctx.sender_key)
            .filter(PrivateMessage.is_read == False)
            .all()
        )

        if not unread_messages:
            return CommandResult.ok("[BBS] Nessun messaggio non letto")

        count = 0
        for msg in unread_messages:
            msg.mark_as_read()
            count += 1

        self.session.commit()

        return CommandResult.ok(
            f"[BBS] {count} messaggi marcati come letti"
        )


@CommandRegistry.register
class StatsCommand(BaseCommand):
    """Show BBS statistics."""

    name = "stats"
    description = "Mostra statistiche BBS"
    usage = "/stats"
    aliases = ["statistics", "stat"]
    admin_only = False

    def __init__(self, session: Session):
        self.session = session

    async def execute(
        self, ctx: CommandContext, args: List[str]
    ) -> CommandResult:
        """
        Execute the stats command.

        Args:
            ctx: Command context
            args: Not used

        Returns:
            BBS statistics
        """
        # Count total users
        total_users = self.session.query(User).count()

        # Count active users (last 24h)
        yesterday = datetime.utcnow() - timedelta(hours=24)
        active_users = (
            self.session.query(User)
            .filter(User.last_seen >= yesterday)
            .filter(User.is_banned == False)
            .count()
        )

        # Count total messages
        total_messages = self.session.query(Message).count()

        # Count messages in last 24h
        recent_messages = (
            self.session.query(Message)
            .filter(Message.timestamp >= yesterday)
            .count()
        )

        # Count total areas
        total_areas = self.session.query(Area).count()
        public_areas = (
            self.session.query(Area)
            .filter(Area.is_public == True)
            .count()
        )

        # Count private messages
        total_pms = self.session.query(PrivateMessage).count()

        # Build response
        lines = [
            "[BBS] Statistiche:",
            f"  Utenti: {total_users} totali, {active_users} attivi (24h)",
            f"  Messaggi: {total_messages} totali, {recent_messages} oggi",
            f"  Aree: {public_areas} pubbliche ({total_areas} totali)",
            f"  PM: {total_pms} totali",
        ]

        return CommandResult.ok("\n".join(lines))


@CommandRegistry.register
class InfoCommand(BaseCommand):
    """Show BBS information."""

    name = "info"
    description = "Informazioni sul BBS"
    usage = "/info"
    aliases = ["about", "version"]
    admin_only = False

    VERSION = "1.0.0"
    BBS_NAME = "MeshCore BBS"

    def __init__(self, session: Session):
        self.session = session

    async def execute(
        self, ctx: CommandContext, args: List[str]
    ) -> CommandResult:
        """
        Execute the info command.

        Args:
            ctx: Command context
            args: Not used

        Returns:
            BBS information
        """
        # Get some stats for context
        total_users = self.session.query(User).count()
        total_areas = (
            self.session.query(Area)
            .filter(Area.is_public == True)
            .count()
        )

        lines = [
            f"[BBS] {self.BBS_NAME} v{self.VERSION}",
            f"  Utenti registrati: {total_users}",
            f"  Aree pubbliche: {total_areas}",
            "  Protocollo: MeshCore LoRa",
            "  Licenza: MIT",
        ]

        return CommandResult.ok("\n".join(lines))


@CommandRegistry.register
class WhoisCommand(BaseCommand):
    """Show information about a user."""

    name = "whois"
    description = "Info su un utente"
    usage = "/whois <utente>"
    aliases = ["user", "profile"]
    admin_only = False

    def __init__(self, session: Session):
        self.session = session
        self.user_repo = UserRepository(session)

    async def execute(
        self, ctx: CommandContext, args: List[str]
    ) -> CommandResult:
        """
        Execute the whois command.

        Args:
            ctx: Command context
            args: [user_identifier]

        Returns:
            User information
        """
        if not args:
            return CommandResult.fail(
                "[BBS] Uso: /whois <utente>\n"
                "Cerca per nickname o chiave pubblica"
            )

        identifier = args[0]

        # Find user
        user = self.user_repo.find_user(identifier)

        if not user:
            return CommandResult.fail(
                f"[BBS] Utente '{identifier}' non trovato"
            )

        # Build response
        lines = [f"[BBS] Profilo: {user.display_name}"]

        # Role
        lines.append(f"  Ruolo: {user.role_display}")

        # Registration date
        first_seen = user.first_seen.strftime("%d/%m/%Y")
        lines.append(f"  Registrato: {first_seen}")

        # Last seen
        last_seen_delta = datetime.utcnow() - user.last_seen
        if last_seen_delta.days > 0:
            last_seen_str = f"{last_seen_delta.days} giorni fa"
        elif last_seen_delta.seconds >= 3600:
            last_seen_str = f"{last_seen_delta.seconds // 3600} ore fa"
        elif last_seen_delta.seconds >= 60:
            last_seen_str = f"{last_seen_delta.seconds // 60} minuti fa"
        else:
            last_seen_str = "online"
        lines.append(f"  Ultimo accesso: {last_seen_str}")

        # Message count
        msg_count = (
            self.session.query(Message)
            .filter(Message.sender_key == user.public_key)
            .count()
        )
        lines.append(f"  Messaggi: {msg_count}")

        # Status (only show if there's something to report)
        if user.is_banned:
            lines.append("  Stato: BANNATO")
        elif user.is_kicked:
            lines.append(f"  Stato: Kick ({user.kick_remaining_minutes} min)")
        elif user.is_muted:
            lines.append("  Stato: Silenziato")

        # Public key (shortened)
        lines.append(f"  Chiave: {user.public_key[:16]}...")

        return CommandResult.ok("\n".join(lines))
