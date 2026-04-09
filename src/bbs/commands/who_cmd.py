"""
Who command for MeshCore BBS.

Shows list of recently active users.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

from datetime import datetime, timedelta
from typing import List

from sqlalchemy.orm import Session

from .base import BaseCommand, CommandContext, CommandResult, CommandRegistry
from bbs.repositories.user_repository import UserRepository


@CommandRegistry.register
class WhoCommand(BaseCommand):
    """Display list of active users."""

    name = "who"
    description = "Mostra utenti attivi"
    usage = "!who [ore]"
    aliases = ["users", "online"]

    # Default hours to look back
    DEFAULT_HOURS = 24
    MAX_HOURS = 168  # 1 week
    MAX_USERS_DISPLAY = 10

    def __init__(self, session: Session):
        self.session = session
        self.user_repo = UserRepository(session)

    async def execute(
        self, ctx: CommandContext, args: List[str]
    ) -> CommandResult:
        """
        Execute the who command.

        Args:
            ctx: Command context
            args: Optional [hours] to look back

        Returns:
            List of active users
        """
        # Parse hours argument
        hours = self.DEFAULT_HOURS
        if args:
            try:
                hours = int(args[0])
                if hours <= 0:
                    return CommandResult.fail(
                        "[BBS] Il numero di ore deve essere positivo"
                    )
                if hours > self.MAX_HOURS:
                    hours = self.MAX_HOURS
            except ValueError:
                return CommandResult.fail(
                    "[BBS] Uso: !who [ore]\nEsempio: !who 12"
                )

        # Get active users
        users = self.user_repo.get_active_users(hours=hours)

        if not users:
            return CommandResult.ok(
                f"[BBS] Nessun utente attivo nelle ultime {hours}h"
            )

        # Build response
        total_users = len(users)
        display_users = users[:self.MAX_USERS_DISPLAY]

        lines = [f"[BBS] Utenti attivi ({total_users}) - ultime {hours}h:"]

        for user in display_users:
            age = self._format_last_seen(user.last_seen)
            name = user.display_name

            # Add role indicator
            role = ""
            if user.is_admin:
                role = " [A]"
            elif user.is_moderator:
                role = " [M]"

            lines.append(f"  {name}{role} ({age})")

        # Show if there are more users
        if total_users > self.MAX_USERS_DISPLAY:
            remaining = total_users - self.MAX_USERS_DISPLAY
            lines.append(f"  ... e altri {remaining}")

        return CommandResult.ok("\n".join(lines))

    def _format_last_seen(self, last_seen: datetime) -> str:
        """
        Format last seen time in a compact way.

        Args:
            last_seen: Datetime of last activity

        Returns:
            Formatted string like "2h", "30m", "ora"
        """
        if last_seen is None:
            return "?"

        delta = datetime.utcnow() - last_seen

        if delta.days > 0:
            return f"{delta.days}g"

        hours = delta.seconds // 3600
        if hours > 0:
            return f"{hours}h"

        minutes = delta.seconds // 60
        if minutes > 0:
            return f"{minutes}m"

        return "ora"
