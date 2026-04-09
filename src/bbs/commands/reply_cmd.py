"""
Reply command for MeshCore BBS.

Reply to a message creating a thread.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

from typing import List

from sqlalchemy.orm import Session

from .base import BaseCommand, CommandContext, CommandResult, CommandRegistry
from bbs.repositories.message_repository import MessageRepository
from bbs.repositories.user_repository import UserRepository
from bbs.mentions import process_mentions_in_message


@CommandRegistry.register
class ReplyCommand(BaseCommand):
    """Reply to a message, creating a threaded conversation."""

    name = "reply"
    description = "Rispondi a un messaggio"
    usage = "/reply <id> <messaggio>"
    aliases = ["re"]

    MAX_MESSAGE_LENGTH = 200

    def __init__(self, session: Session):
        self.session = session
        self.message_repo = MessageRepository(session)
        self.user_repo = UserRepository(session)

    async def execute(
        self, ctx: CommandContext, args: List[str]
    ) -> CommandResult:
        """
        Execute the reply command.

        Args:
            ctx: Command context
            args: [message_id, reply_text...]

        Returns:
            Confirmation or error
        """
        # Check arguments
        if len(args) < 2:
            return CommandResult.fail(
                "[BBS] Uso: /reply <id> <messaggio>\n"
                "Esempio: /reply 42 Sono d'accordo!"
            )

        # Parse message ID
        try:
            parent_id = int(args[0].lstrip("#"))
        except ValueError:
            return CommandResult.fail("[BBS] ID non valido")

        # Get reply text
        reply_text = " ".join(args[1:])

        # Validate message length
        if len(reply_text) > self.MAX_MESSAGE_LENGTH:
            return CommandResult.fail(
                f"[BBS] Messaggio troppo lungo (max {self.MAX_MESSAGE_LENGTH} char)"
            )

        # Get parent message
        parent_message = self.message_repo.get_message_with_author(parent_id)
        if not parent_message:
            return CommandResult.fail(
                f"[BBS] Messaggio #{parent_id} non trovato"
            )

        # Get or create user
        user, _ = self.user_repo.get_or_create(ctx.sender_key)

        # Check if user can post
        if not user.can_post():
            return CommandResult.fail("[BBS] Non puoi pubblicare messaggi")

        # Create reply in same area as parent
        area_name = parent_message.area.name if parent_message.area else "generale"

        message = self.message_repo.create_message(
            area_name=area_name,
            sender_key=ctx.sender_key,
            body=reply_text,
            parent_id=parent_id,
            hops=ctx.hops,
            rssi=ctx.rssi,
        )

        if not message:
            return CommandResult.fail("[BBS] Errore nella creazione della risposta")

        # Commit to get the ID
        self.session.flush()

        # Process @mentions in the reply
        sender_name = user.display_name
        process_mentions_in_message(
            session=self.session,
            message_body=reply_text,
            sender_key=ctx.sender_key,
            sender_name=sender_name,
            message_id=message.id,
            area_name=area_name,
        )

        # Format success response
        parent_author = (
            parent_message.author.display_name
            if parent_message.author
            else parent_message.sender_key[:8]
        )

        return CommandResult.ok(
            f"[BBS] Risposta #{message.id} a #{parent_id} ({parent_author}) pubblicata"
        )
