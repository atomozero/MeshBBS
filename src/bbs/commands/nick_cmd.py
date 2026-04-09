"""
Nick command for MeshCore BBS.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

import re
from typing import List

from sqlalchemy.orm import Session

from .base import BaseCommand, CommandContext, CommandResult, CommandRegistry
from bbs.repositories.user_repository import UserRepository


@CommandRegistry.register
class NickCommand(BaseCommand):
    """Set your nickname."""

    name = "nick"
    description = "Imposta il tuo nickname"
    usage = "!nick <nome>"
    aliases = ["nickname", "name"]

    MIN_LENGTH = 2
    MAX_LENGTH = 16
    VALID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")

    def __init__(self, session: Session):
        self.session = session
        self.user_repo = UserRepository(session)

    async def execute(
        self, ctx: CommandContext, args: List[str]
    ) -> CommandResult:
        """
        Execute the nick command.

        Sets or shows the user's nickname.
        """
        # No argument - show current nickname
        if not args:
            user, _ = self.user_repo.get_or_create(ctx.sender_key)
            if user.nickname:
                return CommandResult.ok(
                    f"[BBS] Il tuo nick: {user.nickname}"
                )
            else:
                return CommandResult.ok(
                    f"[BBS] Nessun nick impostato. Usa: !nick <nome>"
                )

        nickname = args[0]

        # Validate length
        if len(nickname) < self.MIN_LENGTH:
            return CommandResult.fail(
                f"[BBS] Nick troppo corto (min {self.MIN_LENGTH} car)"
            )

        if len(nickname) > self.MAX_LENGTH:
            return CommandResult.fail(
                f"[BBS] Nick troppo lungo (max {self.MAX_LENGTH} car)"
            )

        # Validate characters
        if not self.VALID_PATTERN.match(nickname):
            return CommandResult.fail(
                "[BBS] Nick non valido. Usa solo lettere, numeri, - e _"
            )

        # Check if nickname is already taken
        existing = self.user_repo.get_by_nickname(nickname)
        if existing and existing.public_key != ctx.sender_key:
            return CommandResult.fail(
                f"[BBS] Nick '{nickname}' gia in uso"
            )

        # Set nickname
        user = self.user_repo.set_nickname(ctx.sender_key, nickname)

        if user:
            return CommandResult.ok(f"[BBS] Nick impostato: {nickname}")
        else:
            return CommandResult.fail("[BBS] Errore impostazione nick")
