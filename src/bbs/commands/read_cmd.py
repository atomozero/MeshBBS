"""
Read command for MeshCore BBS.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

from typing import List

from sqlalchemy.orm import Session

from .base import BaseCommand, CommandContext, CommandResult, CommandRegistry
from bbs.repositories.message_repository import MessageRepository


@CommandRegistry.register
class ReadCommand(BaseCommand):
    """Read a specific message by ID."""

    name = "read"
    description = "Leggi un messaggio"
    usage = "!read <id>"
    aliases = ["r"]

    MAX_RESPONSE_LENGTH = 180

    def __init__(self, session: Session):
        self.session = session
        self.message_repo = MessageRepository(session)

    async def execute(
        self, ctx: CommandContext, args: List[str]
    ) -> CommandResult:
        """
        Execute the read command.

        Shows the full content of a specific message.
        """
        # Check for message ID
        if not args:
            return CommandResult.fail(
                f"[BBS] Uso: {self.usage}"
            )

        # Parse message ID
        try:
            msg_id = int(args[0].lstrip("#"))
        except ValueError:
            return CommandResult.fail("[BBS] ID non valido")

        # Get message
        message = self.message_repo.get_message_with_author(msg_id)

        if not message:
            return CommandResult.fail(f"[BBS] Msg #{msg_id} non trovato")

        # Format response
        author = (
            message.author.display_name
            if message.author
            else message.sender_key[:8]
        )
        area = message.area.name if message.area else "?"
        age = message.age_string

        # Build header with threading info
        header = f"[BBS] #{msg_id} in {area}"
        if message.is_reply and message.parent:
            parent_author = (
                message.parent.author.display_name
                if message.parent.author
                else message.parent.sender_key[:8]
            )
            header += f" (re: #{message.parent_id} {parent_author})"

        response = (
            f"{header}\n"
            f"Da: {author} ({age})\n"
            f"{message.body}"
        )

        # Add reply count if any
        if message.reply_count > 0:
            response += f"\n[{message.reply_count} risposte]"

        # Add reply hint
        response += f"\nRispondi: !reply {msg_id} <testo>"

        # Truncate if too long (but keep the reply hint)
        if len(response) > self.MAX_RESPONSE_LENGTH + 50:
            # Truncate body, keep structure
            max_body = self.MAX_RESPONSE_LENGTH - len(header) - len(f"Da: {author} ({age})\n") - 50
            truncated_body = message.body[:max_body] + "..." if len(message.body) > max_body else message.body
            response = (
                f"{header}\n"
                f"Da: {author} ({age})\n"
                f"{truncated_body}"
            )
            if message.reply_count > 0:
                response += f"\n[{message.reply_count} risposte]"
            response += f"\nRispondi: !reply {msg_id} <testo>"

        return CommandResult.ok(response)
