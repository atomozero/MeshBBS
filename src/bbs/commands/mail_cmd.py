"""
Mail command for MeshCore BBS.

Email-like messaging with subject lines. Persistent, searchable.
Different from PM (!msg) which is more like instant messaging.

MIT License - Copyright (c) 2026 MeshBBS Contributors

Commands:
  !mail <user> <subject> | <body>   Send a mail
  !mailbox                          View inbox
  !readmail <id>                    Read a mail
  !delmail <id>                     Delete a mail
"""

from datetime import datetime
from typing import List

from sqlalchemy.orm import Session

from .base import BaseCommand, CommandContext, CommandResult, CommandRegistry
from bbs.models.user import User
from bbs.models.private_message import PrivateMessage
from bbs.repositories.user_repository import UserRepository


@CommandRegistry.register
class MailCommand(BaseCommand):
    """Send a mail with subject."""

    name = "mail"
    description = "Invia una mail con oggetto"
    usage = "!mail <utente> <oggetto> | <corpo>\n  !mail Mario Riunione | Ci vediamo domani alle 10"

    def __init__(self, session: Session):
        self.session = session
        self.user_repo = UserRepository(session)

    async def execute(
        self, ctx: CommandContext, args: List[str]
    ) -> CommandResult:
        if len(args) < 2:
            return CommandResult.fail(
                "[BBS] Uso: !mail <utente> <oggetto> | <corpo>"
            )

        # Find recipient
        recipient_name = args[0]
        recipient = self.user_repo.find_by_nickname(recipient_name)
        if not recipient:
            return CommandResult.fail(f"[BBS] Utente '{recipient_name}' non trovato")

        if recipient.public_key == ctx.sender_key:
            return CommandResult.fail("[BBS] Non puoi inviare mail a te stesso")

        # Parse subject and body (separated by |)
        rest = " ".join(args[1:])
        if "|" in rest:
            subject, body = rest.split("|", 1)
            subject = subject.strip()
            body = body.strip()
        else:
            subject = rest
            body = ""

        if not subject:
            return CommandResult.fail("[BBS] Oggetto mancante")

        # Store as PM with subject in body (format: [MAIL:subject]\nbody)
        mail_body = f"[MAIL:{subject}]\n{body}" if body else f"[MAIL:{subject}]"

        pm = PrivateMessage(
            sender_key=ctx.sender_key,
            recipient_key=recipient.public_key,
            body=mail_body,
        )
        self.session.add(pm)
        self.session.commit()

        sender_name = ctx.sender_display
        return CommandResult.ok(
            f"[BBS] Mail inviata a {recipient.display_name}\n"
            f"  Oggetto: {subject}"
        )


@CommandRegistry.register
class MailboxCommand(BaseCommand):
    """View mail inbox."""

    name = "mailbox"
    description = "Mostra la casella mail"
    usage = "!mailbox"
    aliases = ["mbox"]

    def __init__(self, session: Session):
        self.session = session

    async def execute(
        self, ctx: CommandContext, args: List[str]
    ) -> CommandResult:
        # Get all PMs that are mails (body starts with [MAIL:)
        pms = (
            self.session.query(PrivateMessage)
            .filter(
                PrivateMessage.recipient_key == ctx.sender_key,
                PrivateMessage.body.like("[MAIL:%")
            )
            .order_by(PrivateMessage.timestamp.desc())
            .limit(10)
            .all()
        )

        if not pms:
            return CommandResult.ok("[BBS] Casella mail vuota")

        lines = ["[BBS] Mail:"]
        for pm in pms:
            sender = self.session.query(User).filter_by(public_key=pm.sender_key).first()
            sender_name = sender.display_name if sender else pm.sender_key[:8]
            read_marker = " " if pm.is_read else "*"

            # Extract subject from body
            subject = _extract_subject(pm.body)
            age = _format_age(pm.timestamp)

            lines.append(f"{read_marker}#{pm.id} {sender_name} ({age}): {subject[:40]}")

        lines.append("!readmail <id> per leggere")
        return CommandResult.ok("\n".join(lines))


@CommandRegistry.register
class ReadMailCommand(BaseCommand):
    """Read a specific mail."""

    name = "readmail"
    description = "Leggi una mail"
    usage = "!readmail <id>"
    aliases = ["rmail"]

    def __init__(self, session: Session):
        self.session = session

    async def execute(
        self, ctx: CommandContext, args: List[str]
    ) -> CommandResult:
        if not args or not args[0].isdigit():
            return CommandResult.fail("[BBS] Uso: !readmail <id>")

        pm_id = int(args[0])
        pm = self.session.query(PrivateMessage).filter_by(id=pm_id).first()

        if not pm:
            return CommandResult.fail(f"[BBS] Mail #{pm_id} non trovata")

        if pm.recipient_key != ctx.sender_key and pm.sender_key != ctx.sender_key:
            return CommandResult.fail("[BBS] Non sei il destinatario")

        # Mark as read
        if not pm.is_read and pm.recipient_key == ctx.sender_key:
            pm.is_read = True
            pm.read_at = datetime.utcnow()
            self.session.commit()

        sender = self.session.query(User).filter_by(public_key=pm.sender_key).first()
        sender_name = sender.display_name if sender else pm.sender_key[:8]
        subject = _extract_subject(pm.body)
        body = _extract_body(pm.body)
        age = _format_age(pm.timestamp)

        lines = [f"[BBS] Mail #{pm.id}"]
        lines.append(f"Da: {sender_name} ({age})")
        lines.append(f"Oggetto: {subject}")
        if body:
            lines.append(body)
        lines.append(f"Rispondi: !mail {sender_name} Re:{subject} | <testo>")

        return CommandResult.ok("\n".join(lines))


@CommandRegistry.register
class DelMailCommand(BaseCommand):
    """Delete a mail."""

    name = "delmail"
    description = "Elimina una mail"
    usage = "!delmail <id>"

    def __init__(self, session: Session):
        self.session = session

    async def execute(
        self, ctx: CommandContext, args: List[str]
    ) -> CommandResult:
        if not args or not args[0].isdigit():
            return CommandResult.fail("[BBS] Uso: !delmail <id>")

        pm_id = int(args[0])
        pm = self.session.query(PrivateMessage).filter_by(id=pm_id).first()

        if not pm:
            return CommandResult.fail(f"[BBS] Mail #{pm_id} non trovata")

        if pm.recipient_key != ctx.sender_key and pm.sender_key != ctx.sender_key:
            return CommandResult.fail("[BBS] Non hai i permessi")

        self.session.delete(pm)
        self.session.commit()

        return CommandResult.ok(f"[BBS] Mail #{pm_id} eliminata")


# Helpers

def _extract_subject(body: str) -> str:
    """Extract subject from mail body format [MAIL:subject]."""
    if body.startswith("[MAIL:"):
        end = body.find("]")
        if end > 6:
            return body[6:end]
    return body[:30]


def _extract_body(body: str) -> str:
    """Extract body text from mail format."""
    if body.startswith("[MAIL:"):
        end = body.find("]")
        if end >= 0 and end + 1 < len(body):
            return body[end + 1:].strip()
    return ""


def _format_age(dt: datetime) -> str:
    """Format timestamp as age string."""
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
