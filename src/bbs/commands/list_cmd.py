"""
List command for MeshCore BBS.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

from typing import List

from sqlalchemy.orm import Session

from .base import BaseCommand, CommandContext, CommandResult, CommandRegistry
from bbs.repositories.message_repository import MessageRepository
from utils.config import get_config


@CommandRegistry.register
class ListCommand(BaseCommand):
    """List recent messages in the current area."""

    name = "list"
    description = "Lista ultimi messaggi"
    usage = "/list [n]"
    aliases = ["l", "ls"]

    MAX_LIMIT = 10

    def __init__(self, session: Session):
        self.session = session
        self.config = get_config()
        self.message_repo = MessageRepository(session)

    async def execute(
        self, ctx: CommandContext, args: List[str]
    ) -> CommandResult:
        """
        Execute the list command.

        Shows recent messages from the default area.
        """
        # Parse limit argument
        limit = self.config.messages_per_page

        if args:
            try:
                limit = int(args[0])
                limit = max(1, min(limit, self.MAX_LIMIT))
            except ValueError:
                return CommandResult.fail(
                    "[BBS] Uso: /list [numero]\nEsempio: /list 5"
                )

        # Get recent messages
        messages = self.message_repo.get_recent_messages(
            area_name=self.config.default_area,
            limit=limit,
        )

        if not messages:
            return CommandResult.ok("[BBS] Nessun messaggio")

        # Format message list
        lines = ["[BBS]"]
        for msg in messages:
            author = msg.author.display_name if msg.author else msg.sender_key[:8]
            age = msg.age_string
            preview = msg.preview

            lines.append(f"#{msg.id} {author} ({age}): {preview}")

        return CommandResult.ok("\n".join(lines))
