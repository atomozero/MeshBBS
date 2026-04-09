"""
Advert command for MeshCore BBS.

Allows admins to manually send an advertisement on the mesh network.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

import asyncio
from typing import List

from sqlalchemy.orm import Session

from .base import BaseCommand, CommandContext, CommandResult, CommandRegistry


@CommandRegistry.register
class AdvertCommand(BaseCommand):
    """Send a manual advertisement on the mesh network."""

    name = "advert"
    description = "Invia advertisement sulla rete mesh"
    usage = "!advert"
    aliases = ["announce"]
    admin_only = True

    def __init__(self, session: Session):
        self.session = session

    async def execute(
        self, ctx: CommandContext, args: List[str]
    ) -> CommandResult:
        """Send a flood advert on the mesh network."""
        try:
            from bbs.runtime import get_bbs_instance

            bbs = get_bbs_instance()
            if bbs is None or not bbs._running:
                return CommandResult.fail("[BBS] Servizio BBS non attivo")

            success = await bbs.connection.send_advert(flood=True)

            if success:
                from bbs.models.activity_log import EventType, log_activity
                log_activity(self.session, EventType.ADVERT_SENT, details=f"Manuale da {ctx.sender_display}")
                return CommandResult.ok("[BBS] Advertisement inviato sulla rete mesh")
            else:
                return CommandResult.fail("[BBS] Invio advertisement fallito")

        except ImportError:
            return CommandResult.fail("[BBS] Comando disponibile solo con il launcher")
        except Exception as e:
            return CommandResult.fail(f"[BBS] Errore: {e}")
