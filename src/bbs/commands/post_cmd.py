"""
Post command for MeshCore BBS.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

from typing import List, Tuple, Optional

from sqlalchemy.orm import Session

from .base import BaseCommand, CommandContext, CommandResult, CommandRegistry
from bbs.repositories.message_repository import MessageRepository
from bbs.repositories.user_repository import UserRepository
from bbs.repositories.area_repository import AreaRepository
from bbs.mentions import process_mentions_in_message
from utils.config import get_config


@CommandRegistry.register
class PostCommand(BaseCommand):
    """Post a message to an area."""

    name = "post"
    description = "Pubblica un messaggio"
    usage = "!post [#area] <messaggio>"
    aliases = ["p", "say"]

    def __init__(self, session: Session):
        self.session = session
        self.config = get_config()
        self.message_repo = MessageRepository(session)
        self.user_repo = UserRepository(session)
        self.area_repo = AreaRepository(session)

    async def execute(
        self, ctx: CommandContext, args: List[str]
    ) -> CommandResult:
        """
        Execute the post command.

        Supports two formats:
        - /post <messaggio> - posts to default area
        - /post #area <messaggio> - posts to specified area
        - /post area <messaggio> - posts to specified area (if area exists)
        """
        # Check for message content
        if not args:
            return CommandResult.fail(
                "[BBS] Uso: !post [#area] <messaggio>\n"
                "Esempio: !post Ciao!\n"
                "Esempio: !post #tech Domanda tecnica"
            )

        # Parse area and message
        area_name, text = self._parse_area_and_message(args)

        # Check if we have a message
        if not text:
            return CommandResult.fail(
                "[BBS] Uso: !post [#area] <messaggio>"
            )

        # Validate length
        max_len = self.config.max_message_length
        if len(text) > max_len:
            return CommandResult.fail(
                f"[BBS] Messaggio troppo lungo (max {max_len} car)"
            )

        # Verify area exists and is writable
        area = self.area_repo.get_by_name(area_name)
        if not area:
            available = [a.name for a in self.area_repo.get_writable_areas()]
            return CommandResult.fail(
                f"[BBS] Area '{area_name}' non trovata\n"
                f"Aree disponibili: {', '.join(available)}"
            )

        if area.is_readonly:
            return CommandResult.fail(
                f"[BBS] Area '{area_name}' è in sola lettura"
            )

        # Ensure user exists
        user, _ = self.user_repo.get_or_create(ctx.sender_key)

        # Check if user can post
        if not user.can_post():
            return CommandResult.fail("[BBS] Non puoi pubblicare messaggi")

        # Create message
        message = self.message_repo.create_message(
            area_name=area_name,
            sender_key=ctx.sender_key,
            body=text,
            hops=ctx.hops,
            rssi=ctx.rssi,
        )

        if not message:
            return CommandResult.fail(
                "[BBS] Errore nella creazione del messaggio"
            )

        # Commit to get the ID
        self.session.flush()

        # Process @mentions in the message
        sender_name = user.display_name
        notified_users = process_mentions_in_message(
            session=self.session,
            message_body=text,
            sender_key=ctx.sender_key,
            sender_name=sender_name,
            message_id=message.id,
            area_name=area_name,
        )

        # Build response
        if area_name.lower() != self.config.default_area.lower():
            response = f"[BBS] #{message.id} pubblicato in #{area_name}"
        else:
            response = f"[BBS] #{message.id} pubblicato"

        # Add mention notification count if any
        if notified_users:
            response += f" (notificati: {', '.join(notified_users)})"

        return CommandResult.ok(response)

    def _parse_area_and_message(self, args: List[str]) -> Tuple[str, str]:
        """
        Parse area name and message from arguments.

        Supports:
        - #area message... -> (area, message)
        - areaname message... -> (areaname, message) if area exists
        - message... -> (default_area, message)

        Args:
            args: List of arguments

        Returns:
            Tuple of (area_name, message_text)
        """
        if not args:
            return self.config.default_area, ""

        first_arg = args[0]

        # Check for #area syntax
        if first_arg.startswith("#") and len(first_arg) > 1:
            area_name = first_arg[1:].lower()
            message = " ".join(args[1:])
            return area_name, message

        # Check if first arg is an existing area name
        potential_area = self.area_repo.get_by_name(first_arg)
        if potential_area and len(args) > 1:
            # First arg is an area, rest is message
            return potential_area.name, " ".join(args[1:])

        # Default: all args are the message
        return self.config.default_area, " ".join(args)
