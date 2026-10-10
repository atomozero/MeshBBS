"""
Inbox command for MeshCore BBS.

View private messages received, including ephemeral messages and mentions.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

from typing import List

from sqlalchemy.orm import Session

from .base import BaseCommand, CommandContext, CommandResult, CommandRegistry
from bbs.repositories.private_message_repository import PrivateMessageRepository
from . import msg_cmd
from .msg_cmd import get_ephemeral_messages
from bbs.mentions import get_mention_notifier, format_mentions_for_inbox


@CommandRegistry.register
class InboxCommand(BaseCommand):
    """View inbox with received private messages."""

    name = "inbox"
    description = "Mostra messaggi privati ricevuti"
    usage = "!inbox [n]"
    # NB: no "mail" alias: !mail is the MailCommand (send a mail)
    aliases = ["pms"]

    DEFAULT_LIMIT = 4
    MAX_LIMIT = 6
    # Ephemeral PMs are shown in full (they disappear after reading), so
    # only a few per !inbox; the others stay queued for the next !inbox.
    MAX_EPHEMERAL_SHOWN = 3
    # Defensive bound per ephemeral message (!msg! already limits to 200)
    MAX_EPHEMERAL_LEN = 200

    def __init__(self, session: Session):
        self.session = session
        self.pm_repo = PrivateMessageRepository(session)

    async def execute(
        self, ctx: CommandContext, args: List[str]
    ) -> CommandResult:
        """
        Execute the inbox command.

        Args:
            ctx: Command context
            args: Optional [limit]

        Returns:
            List of private messages
        """
        # Parse limit argument
        limit = self.DEFAULT_LIMIT
        if args:
            try:
                limit = int(args[0])
                if limit <= 0:
                    return CommandResult.fail(
                        "[BBS] Il numero deve essere positivo"
                    )
                limit = min(limit, self.MAX_LIMIT)
            except ValueError:
                return CommandResult.fail(
                    "[BBS] Uso: !inbox [numero]"
                )

        # Get and consume ephemeral messages (they disappear after reading)
        ephemeral = get_ephemeral_messages(ctx.sender_key)
        ephemeral_left = 0
        if len(ephemeral) > self.MAX_EPHEMERAL_SHOWN:
            remaining = ephemeral[self.MAX_EPHEMERAL_SHOWN:]
            ephemeral = ephemeral[:self.MAX_EPHEMERAL_SHOWN]
            ephemeral_left = len(remaining)
            # Put back the ones not shown, before any newly arrived ones
            queue = msg_cmd._ephemeral_messages.setdefault(ctx.sender_key, [])
            queue[:0] = remaining

        # Get and consume mentions (they disappear after reading)
        notifier = get_mention_notifier()
        mentions = notifier.get_mentions(ctx.sender_key, clear=True)

        # Get unread count (persistent messages only)
        unread_count = self.pm_repo.get_unread_count(ctx.sender_key)

        # Get persistent messages
        messages = self.pm_repo.get_inbox(
            user_key=ctx.sender_key,
            limit=limit,
        )

        # Check if there's anything to show
        if not messages and not ephemeral and not mentions:
            return CommandResult.ok(
                "[BBS] Nessun messaggio privato"
            )

        # Build response
        lines = []

        # Show ephemeral messages first (if any)
        if ephemeral:
            lines.append(f"[BBS] PM effimeri ({len(ephemeral)}) - spariscono dopo lettura:")
            for eph in ephemeral:
                sender = eph["sender_name"]
                text = eph["message"]
                if len(text) > self.MAX_EPHEMERAL_LEN:
                    text = text[:self.MAX_EPHEMERAL_LEN - 3] + "..."
                lines.append(f"  {sender}: {text}")
            if ephemeral_left:
                lines.append(f"  (+{ephemeral_left} effimeri: ripeti !inbox)")
            lines.append("")

        # Show persistent messages
        if messages:
            lines.append(f"[BBS] Inbox ({unread_count} non letti):")

            for msg in messages:
                # Get sender display name
                sender_name = msg.sender.display_name if msg.sender else msg.sender_key[:8]

                # Mark unread messages
                read_marker = " " if msg.is_read else "*"

                # Format line
                lines.append(
                    f"{read_marker}#{msg.id} {sender_name} ({msg.age_string}): {msg.preview}"
                )

            lines.append("Usa !readpm <id> per leggere")
        elif not ephemeral and not mentions:
            lines.append("[BBS] Nessun messaggio salvato")

        # Show mentions (if any)
        if mentions:
            lines.append(format_mentions_for_inbox(mentions))

        return CommandResult.ok("\n".join(lines))
