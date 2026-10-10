"""
Delete command for MeshCore BBS.

Allows users to delete their own public messages.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

from typing import List

from sqlalchemy.orm import Session

from .base import BaseCommand, CommandContext, CommandResult, CommandRegistry
from bbs.models.message import Message
from .helpers import parse_int


@CommandRegistry.register
class DeleteCommand(BaseCommand):
    """Delete own public message."""

    name = "delete"
    description = "Elimina un tuo messaggio pubblico (staff: qualsiasi)"
    usage = "!delete <id>"
    aliases = ["del"]

    def __init__(self, session: Session):
        self.session = session

    async def execute(
        self, ctx: CommandContext, args: List[str]
    ) -> CommandResult:
        msg_id = parse_int(args[0], strip_hash=True) if args else None
        if msg_id is None:
            return CommandResult.fail("[BBS] Uso: !delete <id>")

        msg = self.session.query(Message).filter_by(id=msg_id).first()

        if not msg:
            return CommandResult.fail(f"[BBS] Messaggio #{msg_id} non trovato")

        # Only author, moderator or admin can delete
        if msg.sender_key != ctx.sender_key and not (ctx.is_admin or ctx.is_moderator):
            return CommandResult.fail("[BBS] Solo l'autore o lo staff puo eliminare")

        area = msg.area
        self.session.delete(msg)
        if area is not None:
            area.decrement_message_count()
        self.session.commit()

        return CommandResult.ok(f"[BBS] Messaggio #{msg_id} eliminato")
