"""
!notifiche: enable/disable DM notifications for new PMs, replies, mentions.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

from typing import List

from sqlalchemy.orm import Session

from .base import BaseCommand, CommandContext, CommandResult, CommandRegistry
from bbs.services.notifications import get_user_notify, set_user_notify

_ON = {"on", "si", "sì", "1", "attiva"}
_OFF = {"off", "no", "0", "disattiva"}


@CommandRegistry.register
class NotifyCommand(BaseCommand):
    """Toggle DM notifications for the sender."""

    name = "notifiche"
    description = "Avvisi via DM per nuovi PM, mail, risposte e menzioni"
    usage = "!notifiche [on|off]"
    aliases = ["notify"]

    def __init__(self, session: Session):
        self.session = session

    async def execute(self, ctx: CommandContext, args: List[str]) -> CommandResult:
        if not args:
            state = "attive" if get_user_notify(self.session, ctx.sender_key) else "disattivate"
            return CommandResult.ok(
                f"[BBS] Notifiche {state}. Uso: !notifiche on|off"
            )
        choice = args[0].lower()
        if choice in _ON:
            set_user_notify(self.session, ctx.sender_key, True)
            return CommandResult.ok(
                "[BBS] Notifiche attive: avviso via DM (max 1 ogni 10 min)"
            )
        if choice in _OFF:
            set_user_notify(self.session, ctx.sender_key, False)
            return CommandResult.ok("[BBS] Notifiche disattivate")
        return CommandResult.fail("[BBS] Uso: !notifiche on|off")
