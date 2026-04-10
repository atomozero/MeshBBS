"""
Delete command for MeshCore BBS.

Allows users to delete their own public messages.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

from typing import List

from sqlalchemy.orm import Session

from .base import BaseCommand, CommandContext, CommandResult, CommandRegistry
from bbs.models.message import Message


@CommandRegistry.register
class DeleteCommand(BaseCommand):
    """Delete own public message."""

    name = "delete"
    description = "Elimina un tuo messaggio pubblico"
    usage = "!delete <id>"
    aliases = ["del"]

    def __init__(self, session: Session):
        self.session = session

    async def execute(
        self, ctx: CommandContext, args: List[str]
    ) -> CommandResult:
        if not args or not args[0].isdigit():
            return CommandResult.fail("[BBS] Uso: !delete <id>")

        msg_id = int(args[0])
        msg = self.session.query(Message).filter_by(id=msg_id).first()

        if not msg:
            return CommandResult.fail(f"[BBS] Messaggio #{msg_id} non trovato")

        # Only author or admin can delete
        if msg.sender_key != ctx.sender_key and not ctx.is_admin:
            return CommandResult.fail("[BBS] Solo l'autore o un admin puo eliminare")

        self.session.delete(msg)
        self.session.commit()

        return CommandResult.ok(f"[BBS] Messaggio #{msg_id} eliminato")
