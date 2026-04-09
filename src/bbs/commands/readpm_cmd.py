"""
Read private message command for MeshCore BBS.

Read a specific private message by ID.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

from typing import List

from sqlalchemy.orm import Session

from .base import BaseCommand, CommandContext, CommandResult, CommandRegistry
from bbs.repositories.private_message_repository import PrivateMessageRepository


@CommandRegistry.register
class ReadPmCommand(BaseCommand):
    """Read a specific private message."""

    name = "readpm"
    description = "Leggi un messaggio privato"
    usage = "!readpm <id>"
    aliases = ["rpm", "viewpm"]

    def __init__(self, session: Session):
        self.session = session
        self.pm_repo = PrivateMessageRepository(session)

    async def execute(
        self, ctx: CommandContext, args: List[str]
    ) -> CommandResult:
        """
        Execute the readpm command.

        Args:
            ctx: Command context
            args: [message_id]

        Returns:
            Message content or error
        """
        # Check arguments
        if not args:
            return CommandResult.fail(
                "[BBS] Uso: !readpm <id>"
            )

        # Parse message ID
        try:
            message_id = int(args[0])
        except ValueError:
            return CommandResult.fail(
                "[BBS] ID non valido"
            )

        # Get message (must be sender or recipient)
        message = self.pm_repo.get_message_for_user(
            message_id=message_id,
            user_key=ctx.sender_key,
        )

        if not message:
            return CommandResult.fail(
                f"[BBS] Messaggio #{message_id} non trovato"
            )

        # Mark as read if recipient
        if message.recipient_key == ctx.sender_key and not message.is_read:
            self.pm_repo.mark_as_read(message_id, ctx.sender_key)

        # Format response
        # Determine if user is sender or recipient
        if message.sender_key == ctx.sender_key:
            # User is the sender
            other_name = message.recipient.display_name if message.recipient else message.recipient_key[:8]
            direction = f"A: {other_name}"
        else:
            # User is the recipient
            other_name = message.sender.display_name if message.sender else message.sender_key[:8]
            direction = f"Da: {other_name}"

        lines = [
            f"[BBS] PM #{message.id}",
            f"{direction} ({message.age_string})",
            "",
            message.body,
        ]

        # Add reply hint if user is recipient
        if message.recipient_key == ctx.sender_key:
            lines.append("")
            lines.append(f"Rispondi: !msg {other_name} <testo>")

        return CommandResult.ok("\n".join(lines))
