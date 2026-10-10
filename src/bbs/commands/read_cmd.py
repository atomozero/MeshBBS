"""
Read command for MeshCore BBS.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

from typing import List

from sqlalchemy.orm import Session

from .base import BaseCommand, CommandContext, CommandResult, CommandRegistry
from bbs.repositories.message_repository import MessageRepository
from .helpers import parse_int, can_view_area


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
        msg_id = parse_int(args[0], strip_hash=True)
        if msg_id is None:
            return CommandResult.fail("[BBS] ID non valido")

        # Get message
        message = self.message_repo.get_message_with_author(msg_id)

        # Messages in hidden areas are invisible to non-admins
        if not message or (
            message.area is not None and not can_view_area(message.area, ctx)
        ):
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

        replies_suffix = (
            f"\n[{message.reply_count} risp]" if message.reply_count > 0 else ""
        )
        prefix = f"{header}\n{author} ({age})\n"

        response = f"{prefix}{message.body}{replies_suffix}"

        # Truncate body so the full response (including the "[n risp]"
        # suffix) fits in ~2 mesh chunks
        if len(response) > self.MAX_RESPONSE_LENGTH:
            max_body = max(
                0, self.MAX_RESPONSE_LENGTH - len(prefix) - len(replies_suffix) - 3
            )
            response = f"{prefix}{message.body[:max_body]}...{replies_suffix}"

        return CommandResult.ok(response)
