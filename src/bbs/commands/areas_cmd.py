"""
Areas command for MeshCore BBS.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

from typing import List

from sqlalchemy.orm import Session

from .base import BaseCommand, CommandContext, CommandResult, CommandRegistry
from bbs.repositories.area_repository import AreaRepository


@CommandRegistry.register
class AreasCommand(BaseCommand):
    """List available discussion areas."""

    name = "areas"
    description = "Lista aree disponibili"
    usage = "/areas"
    aliases = ["a", "boards"]

    def __init__(self, session: Session):
        self.session = session
        self.area_repo = AreaRepository(session)

    async def execute(
        self, ctx: CommandContext, args: List[str]
    ) -> CommandResult:
        """
        Execute the areas command.

        Lists all public discussion areas.
        """
        areas = self.area_repo.get_public_areas()

        if not areas:
            return CommandResult.ok("[BBS] Nessuna area disponibile")

        # Format area list
        area_names = [area.name for area in areas]

        return CommandResult.ok(
            f"[BBS] Aree: {', '.join(area_names)}"
        )
