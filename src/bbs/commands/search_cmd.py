"""
Search command for MeshCore BBS.

Search messages by content.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from .base import BaseCommand, CommandContext, CommandResult, CommandRegistry
from bbs.repositories.message_repository import MessageRepository
from bbs.repositories.area_repository import AreaRepository
from .helpers import parse_int, can_view_area


@CommandRegistry.register
class SearchCommand(BaseCommand):
    """Search messages by content."""

    name = "search"
    description = "Cerca nei messaggi"
    usage = "!search [#area] <termine>"
    aliases = ["find", "s"]

    DEFAULT_LIMIT = 5
    MAX_LIMIT = 10
    MIN_QUERY_LENGTH = 2

    def __init__(self, session: Session):
        self.session = session
        self.message_repo = MessageRepository(session)
        self.area_repo = AreaRepository(session)

    async def execute(
        self, ctx: CommandContext, args: List[str]
    ) -> CommandResult:
        """
        Execute the search command.

        Supports:
        - !search <term> - search all areas
        - !search #area <term> - search in specific area
        - !search <term> <n> - search with custom limit

        Args:
            ctx: Command context
            args: Search arguments

        Returns:
            Search results or error
        """
        if not args:
            return CommandResult.fail(
                "[BBS] Uso: !search [#area] <termine>\n"
                "Esempio: !search ciao\n"
                "Esempio: !search #tech python"
            )

        # Parse area and query
        area_name, query, limit = self._parse_args(args)

        # Validate query
        if not query:
            return CommandResult.fail(
                "[BBS] Uso: !search [#area] <termine>"
            )

        if len(query) < self.MIN_QUERY_LENGTH:
            return CommandResult.fail(
                f"[BBS] Termine troppo corto (min {self.MIN_QUERY_LENGTH} caratteri)"
            )

        # Validate area if specified
        if area_name:
            area = self.area_repo.get_by_name(area_name)
            # Hidden areas are invisible to non-admins
            if not area or not can_view_area(area, ctx):
                return CommandResult.fail(
                    f"[BBS] Area '{area_name}' non trovata"
                )

        # Search messages
        # Fetch extra rows so that filtering out hidden areas (non-admins)
        # still leaves up to `limit` results.
        fetch_limit = limit if ctx.is_admin else limit * 4
        messages = self.message_repo.search_messages(
            query=query,
            area_name=area_name,
            limit=fetch_limit,
        )
        if not ctx.is_admin:
            messages = [
                m for m in messages
                if m.area is None or can_view_area(m.area, ctx)
            ]
        messages = messages[:limit]

        if not messages:
            if area_name:
                return CommandResult.ok(
                    f"[BBS] Nessun risultato per '{query}' in #{area_name}"
                )
            else:
                return CommandResult.ok(
                    f"[BBS] Nessun risultato per '{query}'"
                )

        # Build response
        total = len(messages)
        area_info = f" in #{area_name}" if area_name else ""
        lines = [f"[BBS] {total} risultati per '{query}'{area_info}:"]

        for msg in messages:
            author = msg.author.display_name if msg.author else msg.sender_key[:8]
            area = msg.area.name if msg.area else "?"

            # Highlight search term in preview
            preview = self._make_preview(msg.body, query)

            lines.append(f"  #{msg.id} [{area}] {author}: {preview}")

        lines.append("Usa !read <id> per leggere")

        return CommandResult.ok("\n".join(lines))

    def _parse_args(self, args: List[str]) -> Tuple[Optional[str], str, int]:
        """
        Parse search arguments.

        Args:
            args: List of arguments

        Returns:
            Tuple of (area_name, query, limit)
        """
        area_name = None
        limit = self.DEFAULT_LIMIT
        query_parts = []

        for arg in args:
            # Check for #area
            if arg.startswith("#") and len(arg) > 1 and not area_name:
                area_name = arg[1:].lower()
            # Number after query is limit (a leading number is query text)
            elif query_parts and parse_int(arg) is not None:
                limit = max(1, min(parse_int(arg), self.MAX_LIMIT))
            else:
                query_parts.append(arg)

        query = " ".join(query_parts)
        return area_name, query, limit

    def _make_preview(self, body: str, query: str, max_len: int = 40) -> str:
        """
        Create a preview of the message highlighting the search term.

        Args:
            body: Message body
            query: Search term
            max_len: Maximum preview length

        Returns:
            Preview string
        """
        # Find query position (case-insensitive)
        lower_body = body.lower()
        lower_query = query.lower()
        pos = lower_body.find(lower_query)

        if pos == -1:
            # Query not found, just truncate
            if len(body) <= max_len:
                return body
            return body[:max_len - 3] + "..."

        # Center the preview around the match
        start = max(0, pos - 10)
        end = min(len(body), pos + len(query) + 20)

        preview = body[start:end]

        # Add ellipsis if truncated
        if start > 0:
            preview = "..." + preview
        if end < len(body):
            preview = preview + "..."

        # Ensure max length
        if len(preview) > max_len:
            preview = preview[:max_len - 3] + "..."

        return preview
