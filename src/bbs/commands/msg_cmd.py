"""
Private message command for MeshCore BBS.

Send private messages to other users.
Supports ephemeral (non-saved) messages with /msg! command.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

from typing import List, Optional

from sqlalchemy.orm import Session

from .base import BaseCommand, CommandContext, CommandResult, CommandRegistry
from bbs.repositories.private_message_repository import PrivateMessageRepository
from bbs.repositories.user_repository import UserRepository

# Store for ephemeral messages (in-memory only, not persisted)
# Key: recipient_key, Value: list of (sender_key, sender_name, message, timestamp)
_ephemeral_messages: dict = {}


def get_ephemeral_messages(recipient_key: str) -> list:
    """Get and clear ephemeral messages for a recipient."""
    messages = _ephemeral_messages.pop(recipient_key, [])
    return messages


def add_ephemeral_message(
    recipient_key: str,
    sender_key: str,
    sender_name: str,
    message: str,
) -> None:
    """Add an ephemeral message for a recipient."""
    from datetime import datetime

    if recipient_key not in _ephemeral_messages:
        _ephemeral_messages[recipient_key] = []

    _ephemeral_messages[recipient_key].append({
        "sender_key": sender_key,
        "sender_name": sender_name,
        "message": message,
        "timestamp": datetime.utcnow(),
    })

    # Limit to 50 ephemeral messages per recipient
    if len(_ephemeral_messages[recipient_key]) > 50:
        _ephemeral_messages[recipient_key] = _ephemeral_messages[recipient_key][-50:]


@CommandRegistry.register
class MsgCommand(BaseCommand):
    """Send a private message to another user."""

    name = "msg"
    description = "Invia un messaggio privato"
    usage = "/msg <utente> <messaggio>"
    aliases = ["pm", "dm", "tell"]

    MAX_MESSAGE_LENGTH = 200

    def __init__(self, session: Session):
        self.session = session
        self.pm_repo = PrivateMessageRepository(session)
        self.user_repo = UserRepository(session)

    async def execute(
        self, ctx: CommandContext, args: List[str]
    ) -> CommandResult:
        """
        Execute the msg command.

        Args:
            ctx: Command context
            args: [recipient, message...]

        Returns:
            Confirmation or error
        """
        # Check arguments
        if len(args) < 2:
            return CommandResult.fail(
                "[BBS] Uso: /msg <utente> <messaggio>\n"
                "Utente: nickname o chiave pubblica (8+ char)"
            )

        recipient_identifier = args[0]
        message_text = " ".join(args[1:])

        # Check if sender can post (not muted)
        sender, _ = self.user_repo.get_or_create(ctx.sender_key)
        if not sender.can_post():
            return CommandResult.fail("[BBS] Non puoi inviare messaggi")

        # Validate message length
        if len(message_text) > self.MAX_MESSAGE_LENGTH:
            return CommandResult.fail(
                f"[BBS] Messaggio troppo lungo (max {self.MAX_MESSAGE_LENGTH} char)"
            )

        # Find recipient
        recipient = self._find_recipient(recipient_identifier)
        if not recipient:
            return CommandResult.fail(
                f"[BBS] Utente '{recipient_identifier}' non trovato"
            )

        # Can't message yourself
        if recipient.public_key == ctx.sender_key:
            return CommandResult.fail(
                "[BBS] Non puoi inviare messaggi a te stesso"
            )

        # Check if recipient is banned
        if recipient.is_banned:
            return CommandResult.fail(
                "[BBS] Impossibile inviare messaggi a questo utente"
            )

        # Send message
        message = self.pm_repo.send_message(
            sender_key=ctx.sender_key,
            recipient_key=recipient.public_key,
            body=message_text,
        )

        if not message:
            return CommandResult.fail(
                "[BBS] Errore nell'invio del messaggio"
            )

        # Success
        recipient_name = recipient.display_name
        return CommandResult.ok(
            f"[BBS] Messaggio inviato a {recipient_name}"
        )

    def _find_recipient(self, identifier: str):
        """
        Find a user by nickname or public key.

        Args:
            identifier: Nickname or public key prefix (min 8 chars)

        Returns:
            User or None
        """
        # First try by nickname (exact match, case insensitive)
        user = self.user_repo.get_by_nickname(identifier)
        if user:
            return user

        # Then try by public key prefix (minimum 8 characters)
        if len(identifier) >= 8:
            # Search by public key prefix
            from bbs.models.user import User
            user = (
                self.session.query(User)
                .filter(User.public_key.startswith(identifier.upper()))
                .first()
            )
            if user:
                return user

            # Also try lowercase
            user = (
                self.session.query(User)
                .filter(User.public_key.startswith(identifier.lower()))
                .first()
            )
            if user:
                return user

        return None


@CommandRegistry.register
class EphemeralMsgCommand(BaseCommand):
    """Send an ephemeral (non-saved) private message."""

    name = "msg!"
    description = "Invia PM effimero (non salvato)"
    usage = "/msg! <utente> <messaggio>"
    aliases = ["pm!", "dm!"]

    MAX_MESSAGE_LENGTH = 200

    def __init__(self, session: Session):
        self.session = session
        self.user_repo = UserRepository(session)

    async def execute(
        self, ctx: CommandContext, args: List[str]
    ) -> CommandResult:
        """
        Execute the msg! command (ephemeral message).

        The message is NOT saved to the database.
        It only exists in memory until the recipient reads it.

        Args:
            ctx: Command context
            args: [recipient, message...]

        Returns:
            Confirmation or error
        """
        # Check arguments
        if len(args) < 2:
            return CommandResult.fail(
                "[BBS] Uso: /msg! <utente> <messaggio>\n"
                "Il messaggio NON viene salvato nel database"
            )

        recipient_identifier = args[0]
        message_text = " ".join(args[1:])

        # Check if sender can post (not muted)
        sender, _ = self.user_repo.get_or_create(ctx.sender_key)
        if not sender.can_post():
            return CommandResult.fail("[BBS] Non puoi inviare messaggi")

        # Validate message length
        if len(message_text) > self.MAX_MESSAGE_LENGTH:
            return CommandResult.fail(
                f"[BBS] Messaggio troppo lungo (max {self.MAX_MESSAGE_LENGTH} char)"
            )

        # Find recipient
        recipient = self._find_recipient(recipient_identifier)
        if not recipient:
            return CommandResult.fail(
                f"[BBS] Utente '{recipient_identifier}' non trovato"
            )

        # Can't message yourself
        if recipient.public_key == ctx.sender_key:
            return CommandResult.fail(
                "[BBS] Non puoi inviare messaggi a te stesso"
            )

        # Check if recipient is banned
        if recipient.is_banned:
            return CommandResult.fail(
                "[BBS] Impossibile inviare messaggi a questo utente"
            )

        # Add ephemeral message (in-memory only)
        add_ephemeral_message(
            recipient_key=recipient.public_key,
            sender_key=ctx.sender_key,
            sender_name=sender.display_name,
            message=message_text,
        )

        # Success
        recipient_name = recipient.display_name
        return CommandResult.ok(
            f"[BBS] PM effimero inviato a {recipient_name} (non salvato)"
        )

    def _find_recipient(self, identifier: str):
        """Find a user by nickname or public key."""
        user = self.user_repo.get_by_nickname(identifier)
        if user:
            return user

        if len(identifier) >= 8:
            from bbs.models.user import User
            user = (
                self.session.query(User)
                .filter(User.public_key.startswith(identifier.upper()))
                .first()
            )
            if user:
                return user

            user = (
                self.session.query(User)
                .filter(User.public_key.startswith(identifier.lower()))
                .first()
            )
            if user:
                return user

        return None
