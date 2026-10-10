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
from bbs.services.notifications import KIND_REPLY, notify_event
from .helpers import parse_int, can_view_area


@CommandRegistry.register
class ReplyCommand(BaseCommand):
    """Reply to a message, creating a threaded conversation."""

    name = "reply"
    description = "Rispondi a un messaggio"
    usage = "!reply <id> <messaggio>"
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
                "[BBS] Uso: !reply <id> <messaggio>\n"
                "Esempio: !reply 42 Sono d'accordo!"
            )

        # Parse message ID
        parent_id = parse_int(args[0], strip_hash=True)
        if parent_id is None:
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
        parent_area = parent_message.area if parent_message else None
        # Messages in hidden areas are invisible to non-admins
        if not parent_message or (
            parent_area is not None and not can_view_area(parent_area, ctx)
        ):
            return CommandResult.fail(
                f"[BBS] Messaggio #{parent_id} non trovato"
            )

        # Replies obey the same rules as posts in the parent's area
        if parent_area is not None:
            writable = (
                (not parent_area.is_readonly) if ctx.is_admin
                else parent_area.can_post()
            )
            if not writable:
                return CommandResult.fail(
                    f"[BBS] Area '{parent_area.name}' è in sola lettura"
                )

        # Get or create user
        user, _ = self.user_repo.get_or_create(ctx.sender_key)

        # Check if user can post
        if not user.can_post():
            return CommandResult.fail("[BBS] Non puoi pubblicare messaggi")

        # Create reply in same area as parent
        area_name = parent_area.name if parent_area else "generale"

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

        # Notify the author of the parent post (never themself)
        if parent_message.sender_key and parent_message.sender_key != ctx.sender_key:
            notify_event(
                parent_message.sender_key, KIND_REPLY,
                sender_key=ctx.sender_key, sender_name=sender_name, ref=message.id,
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
