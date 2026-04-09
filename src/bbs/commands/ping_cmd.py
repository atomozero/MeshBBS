"""
Ping command for MeshCore BBS.

Simple connectivity test showing BBS response time and signal info.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

from datetime import datetime
from typing import List

from sqlalchemy.orm import Session

from .base import BaseCommand, CommandContext, CommandResult, CommandRegistry


@CommandRegistry.register
class PingCommand(BaseCommand):
    """Test BBS connectivity and response time."""

    name = "ping"
    description = "Test connessione al BBS"
    usage = "!ping"
    aliases = ["pong"]

    def __init__(self, session: Session):
        self.session = session

    async def execute(
        self, ctx: CommandContext, args: List[str]
    ) -> CommandResult:
        now = datetime.utcnow()

        lines = [f"[BBS] Pong!"]

        # Show signal info if available
        if ctx.hops is not None:
            lines.append(f"  Hop: {ctx.hops}")
        if ctx.rssi is not None:
            lines.append(f"  RSSI: {ctx.rssi} dBm")

        lines.append(f"  Ora BBS: {now.strftime('%H:%M:%S UTC')}")

        return CommandResult.ok("\n".join(lines))
