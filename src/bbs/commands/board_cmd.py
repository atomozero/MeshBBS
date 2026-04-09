"""
Board command for MeshCore BBS.

Persistent bulletin board for announcements and notices.
Different from !post (area-based chat) - boards are for
longer-lived content like announcements, rules, events.

MIT License - Copyright (c) 2026 MeshBBS Contributors

Commands:
  !board                   View latest board posts
  !board post <text>       Post to the board
  !board read <id>         Read full post
  !board del <id>          Delete post (admin only)
"""

from datetime import datetime
from typing import List

from sqlalchemy.orm import Session

from .base import BaseCommand, CommandContext, CommandResult, CommandRegistry
from bbs.models.message import Message
from bbs.models.area import Area
from bbs.models.user import User

BOARD_AREA_NAME = "bacheca"


def _ensure_board_area(session: Session) -> Area:
    """Get or create the board area."""
    area = session.query(Area).filter_by(name=BOARD_AREA_NAME).first()
    if not area:
        area = Area(
            name=BOARD_AREA_NAME,
            description="Bacheca annunci",
            is_public=True,
            is_readonly=False,
        )
        session.add(area)
        session.commit()
    return area


@CommandRegistry.register
class BoardCommand(BaseCommand):
    """Bulletin board for announcements."""

    name = "board"
    description = "Bacheca annunci"
    usage = "!board\n  !board post <testo>\n  !board read <id>\n  !board del <id>"
    aliases = ["bacheca", "bb"]

    def __init__(self, session: Session):
        self.session = session

    async def execute(
        self, ctx: CommandContext, args: List[str]
    ) -> CommandResult:
        if not args:
            return self._list_posts()

        subcmd = args[0].lower()

        if subcmd == "post" and len(args) > 1:
            return self._create_post(ctx, " ".join(args[1:]))
        elif subcmd == "read" and len(args) > 1 and args[1].isdigit():
            return self._read_post(ctx, int(args[1]))
        elif subcmd == "del" and len(args) > 1 and args[1].isdigit():
            return self._delete_post(ctx, int(args[1]))
        else:
            return CommandResult.fail(
                "[BBS] Uso:\n"
                "  !board - ultimi annunci\n"
                "  !board post <testo>\n"
                "  !board read <id>\n"
                "  !board del <id> (admin)"
            )

    def _list_posts(self) -> CommandResult:
        """List latest board posts."""
        area = _ensure_board_area(self.session)

        posts = (
            self.session.query(Message)
            .filter_by(area_id=area.id)
            .order_by(Message.timestamp.desc())
            .limit(5)
            .all()
        )

        if not posts:
            return CommandResult.ok("[BBS] Bacheca vuota. Scrivi con !board post <testo>")

        lines = ["[BBS] Bacheca:"]
        for p in posts:
            author = p.author.display_name if p.author else p.sender_key[:8]
            age = _format_age(p.timestamp)
            preview = p.body[:50] + ("..." if len(p.body) > 50 else "")
            lines.append(f"  #{p.id} {author} ({age}): {preview}")

        lines.append("!board read <id> per leggere")
        return CommandResult.ok("\n".join(lines))

    def _create_post(self, ctx: CommandContext, text: str) -> CommandResult:
        """Create a new board post."""
        if len(text) > 500:
            return CommandResult.fail("[BBS] Post troppo lungo (max 500 caratteri)")

        area = _ensure_board_area(self.session)

        post = Message(
            area_id=area.id,
            sender_key=ctx.sender_key,
            body=text,
        )
        self.session.add(post)
        area.message_count = (area.message_count or 0) + 1
        area.last_post_at = datetime.utcnow()
        self.session.commit()

        return CommandResult.ok(f"[BBS] Annuncio #{post.id} pubblicato in bacheca")

    def _read_post(self, ctx: CommandContext, post_id: int) -> CommandResult:
        """Read a full board post."""
        area = _ensure_board_area(self.session)

        post = (
            self.session.query(Message)
            .filter_by(id=post_id, area_id=area.id)
            .first()
        )

        if not post:
            return CommandResult.fail(f"[BBS] Annuncio #{post_id} non trovato")

        author = post.author.display_name if post.author else post.sender_key[:8]
        age = _format_age(post.timestamp)

        return CommandResult.ok(
            f"[BBS] Bacheca #{post.id}\n"
            f"Da: {author} ({age})\n"
            f"{post.body}"
        )

    def _delete_post(self, ctx: CommandContext, post_id: int) -> CommandResult:
        """Delete a board post (admin or author only)."""
        area = _ensure_board_area(self.session)

        post = (
            self.session.query(Message)
            .filter_by(id=post_id, area_id=area.id)
            .first()
        )

        if not post:
            return CommandResult.fail(f"[BBS] Annuncio #{post_id} non trovato")

        # Only admin or author can delete
        if post.sender_key != ctx.sender_key and not ctx.is_admin:
            return CommandResult.fail("[BBS] Solo l'autore o un admin puo eliminare")

        self.session.delete(post)
        self.session.commit()

        return CommandResult.ok(f"[BBS] Annuncio #{post_id} eliminato")


def _format_age(dt: datetime) -> str:
    if not dt:
        return "?"
    diff = (datetime.utcnow() - dt).total_seconds()
    if diff < 60:
        return "ora"
    if diff < 3600:
        return f"{int(diff / 60)}m"
    if diff < 86400:
        return f"{int(diff / 3600)}h"
    return f"{int(diff / 86400)}g"
