"""
Admin commands for MeshCore BBS.

Commands for user moderation: ban, unban, mute, unmute, promote, demote.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

from typing import List

from sqlalchemy.orm import Session

from .base import BaseCommand, CommandContext, CommandResult, CommandRegistry
from bbs.repositories.user_repository import UserRepository


@CommandRegistry.register
class BanCommand(BaseCommand):
    """Ban a user from the BBS."""

    name = "ban"
    description = "Banna un utente"
    usage = "!ban <utente> [motivo]"
    aliases = []
    admin_only = True

    def __init__(self, session: Session):
        self.session = session
        self.user_repo = UserRepository(session)

    async def execute(
        self, ctx: CommandContext, args: List[str]
    ) -> CommandResult:
        """
        Execute the ban command.

        Args:
            ctx: Command context
            args: [user_identifier, ...reason]

        Returns:
            Result of the ban operation
        """
        if not args:
            return CommandResult.fail(
                "[BBS] Uso: !ban <utente> [motivo]\n"
                "Esempio: !ban Mario spam\n"
                "Esempio: !ban abc12345 comportamento scorretto"
            )

        user_identifier = args[0]
        reason = " ".join(args[1:]) if len(args) > 1 else None

        # Find target user
        target = self.user_repo.find_user(user_identifier)

        if not target:
            return CommandResult.fail(
                f"[BBS] Utente '{user_identifier}' non trovato"
            )

        # Cannot ban yourself
        if target.public_key == ctx.sender_key:
            return CommandResult.fail("[BBS] Non puoi bannare te stesso")

        # Cannot ban admins
        if target.is_admin:
            return CommandResult.fail("[BBS] Non puoi bannare un admin")

        # Check if already banned
        if target.is_banned:
            return CommandResult.fail(
                f"[BBS] {target.display_name} è già bannato"
            )

        # Perform ban
        self.user_repo.ban_user(target.public_key, reason)
        self.session.commit()

        reason_text = f" - Motivo: {reason}" if reason else ""
        return CommandResult.ok(
            f"[BBS] {target.display_name} è stato bannato{reason_text}"
        )


@CommandRegistry.register
class UnbanCommand(BaseCommand):
    """Remove ban from a user."""

    name = "unban"
    description = "Rimuove il ban da un utente"
    usage = "!unban <utente>"
    aliases = []
    admin_only = True

    def __init__(self, session: Session):
        self.session = session
        self.user_repo = UserRepository(session)

    async def execute(
        self, ctx: CommandContext, args: List[str]
    ) -> CommandResult:
        """
        Execute the unban command.

        Args:
            ctx: Command context
            args: [user_identifier]

        Returns:
            Result of the unban operation
        """
        if not args:
            return CommandResult.fail(
                "[BBS] Uso: !unban <utente>\n"
                "Esempio: !unban Mario"
            )

        user_identifier = args[0]

        # Find target user
        target = self.user_repo.find_user(user_identifier)

        if not target:
            return CommandResult.fail(
                f"[BBS] Utente '{user_identifier}' non trovato"
            )

        # Check if not banned
        if not target.is_banned:
            return CommandResult.fail(
                f"[BBS] {target.display_name} non è bannato"
            )

        # Perform unban
        self.user_repo.unban_user(target.public_key)
        self.session.commit()

        return CommandResult.ok(
            f"[BBS] Il ban di {target.display_name} è stato rimosso"
        )


@CommandRegistry.register
class MuteCommand(BaseCommand):
    """Mute a user (can read but not post)."""

    name = "mute"
    description = "Silenzia un utente"
    usage = "!mute <utente> [motivo]"
    aliases = ["silence"]
    admin_only = True

    def __init__(self, session: Session):
        self.session = session
        self.user_repo = UserRepository(session)

    async def execute(
        self, ctx: CommandContext, args: List[str]
    ) -> CommandResult:
        """
        Execute the mute command.

        Args:
            ctx: Command context
            args: [user_identifier, ...reason]

        Returns:
            Result of the mute operation
        """
        if not args:
            return CommandResult.fail(
                "[BBS] Uso: !mute <utente> [motivo]\n"
                "Esempio: !mute Mario off-topic\n"
                "L'utente potrà leggere ma non scrivere"
            )

        user_identifier = args[0]
        reason = " ".join(args[1:]) if len(args) > 1 else None

        # Find target user
        target = self.user_repo.find_user(user_identifier)

        if not target:
            return CommandResult.fail(
                f"[BBS] Utente '{user_identifier}' non trovato"
            )

        # Cannot mute yourself
        if target.public_key == ctx.sender_key:
            return CommandResult.fail("[BBS] Non puoi silenziare te stesso")

        # Cannot mute admins
        if target.is_admin:
            return CommandResult.fail("[BBS] Non puoi silenziare un admin")

        # Check if banned (banned users don't need mute)
        if target.is_banned:
            return CommandResult.fail(
                f"[BBS] {target.display_name} è bannato (non può già accedere)"
            )

        # Check if already muted
        if target.is_muted:
            return CommandResult.fail(
                f"[BBS] {target.display_name} è già silenziato"
            )

        # Perform mute
        self.user_repo.mute_user(target.public_key, reason)
        self.session.commit()

        reason_text = f" - Motivo: {reason}" if reason else ""
        return CommandResult.ok(
            f"[BBS] {target.display_name} è stato silenziato{reason_text}"
        )


@CommandRegistry.register
class UnmuteCommand(BaseCommand):
    """Remove mute from a user."""

    name = "unmute"
    description = "Rimuove il silenziamento da un utente"
    usage = "!unmute <utente>"
    aliases = ["unsilence"]
    admin_only = True

    def __init__(self, session: Session):
        self.session = session
        self.user_repo = UserRepository(session)

    async def execute(
        self, ctx: CommandContext, args: List[str]
    ) -> CommandResult:
        """
        Execute the unmute command.

        Args:
            ctx: Command context
            args: [user_identifier]

        Returns:
            Result of the unmute operation
        """
        if not args:
            return CommandResult.fail(
                "[BBS] Uso: !unmute <utente>\n"
                "Esempio: !unmute Mario"
            )

        user_identifier = args[0]

        # Find target user
        target = self.user_repo.find_user(user_identifier)

        if not target:
            return CommandResult.fail(
                f"[BBS] Utente '{user_identifier}' non trovato"
            )

        # Check if not muted
        if not target.is_muted:
            return CommandResult.fail(
                f"[BBS] {target.display_name} non è silenziato"
            )

        # Perform unmute
        self.user_repo.unmute_user(target.public_key)
        self.session.commit()

        return CommandResult.ok(
            f"[BBS] {target.display_name} può nuovamente scrivere"
        )


@CommandRegistry.register
class PromoteCommand(BaseCommand):
    """Promote a user to moderator or admin."""

    name = "promote"
    description = "Promuovi un utente a moderatore o admin"
    usage = "!promote <utente> [admin]"
    aliases = []
    admin_only = True

    def __init__(self, session: Session):
        self.session = session
        self.user_repo = UserRepository(session)

    async def execute(
        self, ctx: CommandContext, args: List[str]
    ) -> CommandResult:
        """
        Execute the promote command.

        Args:
            ctx: Command context
            args: [user_identifier, optional "admin"]

        Returns:
            Result of the promote operation
        """
        if not args:
            return CommandResult.fail(
                "[BBS] Uso: !promote <utente> [admin]\n"
                "Esempio: !promote Mario - promuove a moderatore\n"
                "Esempio: !promote Mario admin - promuove ad admin"
            )

        user_identifier = args[0]
        promote_to_admin = len(args) > 1 and args[1].lower() == "admin"

        # Find target user
        target = self.user_repo.find_user(user_identifier)

        if not target:
            return CommandResult.fail(
                f"[BBS] Utente '{user_identifier}' non trovato"
            )

        # Cannot promote yourself
        if target.public_key == ctx.sender_key:
            return CommandResult.fail("[BBS] Non puoi promuovere te stesso")

        # Check if banned
        if target.is_banned:
            return CommandResult.fail(
                f"[BBS] {target.display_name} è bannato"
            )

        if promote_to_admin:
            # Promote to admin
            if target.is_admin:
                return CommandResult.fail(
                    f"[BBS] {target.display_name} è già admin"
                )

            self.user_repo.promote_to_admin(target.public_key)
            self.session.commit()

            return CommandResult.ok(
                f"[BBS] {target.display_name} è ora Admin"
            )
        else:
            # Promote to moderator
            if target.is_admin:
                return CommandResult.fail(
                    f"[BBS] {target.display_name} è già admin"
                )

            if target.is_moderator:
                return CommandResult.fail(
                    f"[BBS] {target.display_name} è già moderatore"
                )

            self.user_repo.promote_to_moderator(target.public_key)
            self.session.commit()

            return CommandResult.ok(
                f"[BBS] {target.display_name} è ora Moderatore"
            )


@CommandRegistry.register
class DemoteCommand(BaseCommand):
    """Demote a user from moderator or admin."""

    name = "demote"
    description = "Rimuovi ruolo moderatore o admin"
    usage = "!demote <utente>"
    aliases = []
    admin_only = True

    def __init__(self, session: Session):
        self.session = session
        self.user_repo = UserRepository(session)

    async def execute(
        self, ctx: CommandContext, args: List[str]
    ) -> CommandResult:
        """
        Execute the demote command.

        Args:
            ctx: Command context
            args: [user_identifier]

        Returns:
            Result of the demote operation
        """
        if not args:
            return CommandResult.fail(
                "[BBS] Uso: !demote <utente>\n"
                "Esempio: !demote Mario\n"
                "Admin diventa moderatore, moderatore diventa utente"
            )

        user_identifier = args[0]

        # Find target user
        target = self.user_repo.find_user(user_identifier)

        if not target:
            return CommandResult.fail(
                f"[BBS] Utente '{user_identifier}' non trovato"
            )

        # Cannot demote yourself
        if target.public_key == ctx.sender_key:
            return CommandResult.fail("[BBS] Non puoi degradare te stesso")

        # Check current role
        if not target.is_admin and not target.is_moderator:
            return CommandResult.fail(
                f"[BBS] {target.display_name} è già un utente normale"
            )

        old_role = target.role_display

        if target.is_admin:
            # Demote from admin to moderator
            self.user_repo.demote_from_admin(target.public_key)
            self.session.commit()

            return CommandResult.ok(
                f"[BBS] {target.display_name} è ora Moderatore (era {old_role})"
            )
        else:
            # Demote from moderator to user
            self.user_repo.demote_from_moderator(target.public_key)
            self.session.commit()

            return CommandResult.ok(
                f"[BBS] {target.display_name} è ora Utente (era {old_role})"
            )


@CommandRegistry.register
class StaffCommand(BaseCommand):
    """List all staff members (admins and moderators)."""

    name = "staff"
    description = "Mostra lo staff del BBS"
    usage = "!staff"
    aliases = ["mods", "admins"]
    admin_only = False  # Everyone can see staff

    def __init__(self, session: Session):
        self.session = session
        self.user_repo = UserRepository(session)

    async def execute(
        self, ctx: CommandContext, args: List[str]
    ) -> CommandResult:
        """
        Execute the staff command.

        Args:
            ctx: Command context
            args: Not used

        Returns:
            List of staff members
        """
        admins = self.user_repo.get_admins()
        moderators = self.user_repo.get_moderators()

        if not admins and not moderators:
            return CommandResult.ok("[BBS] Nessuno staff configurato")

        lines = ["[BBS] Staff:"]

        if admins:
            admin_names = [f"  [A] {u.display_name}" for u in admins]
            lines.extend(admin_names)

        if moderators:
            mod_names = [f"  [M] {u.display_name}" for u in moderators]
            lines.extend(mod_names)

        lines.append(f"Totale: {len(admins)} admin, {len(moderators)} mod")

        return CommandResult.ok("\n".join(lines))


@CommandRegistry.register
class KickCommand(BaseCommand):
    """Kick a user temporarily."""

    name = "kick"
    description = "Espelli temporaneamente un utente"
    usage = "!kick <utente> <minuti> [motivo]"
    aliases = []
    admin_only = True

    DEFAULT_MINUTES = 30
    MAX_MINUTES = 1440  # 24 hours

    def __init__(self, session: Session):
        self.session = session
        self.user_repo = UserRepository(session)

    async def execute(
        self, ctx: CommandContext, args: List[str]
    ) -> CommandResult:
        """
        Execute the kick command.

        Args:
            ctx: Command context
            args: [user_identifier, minutes, ...reason]

        Returns:
            Result of the kick operation
        """
        if not args:
            return CommandResult.fail(
                "[BBS] Uso: !kick <utente> [minuti] [motivo]\n"
                f"Default: {self.DEFAULT_MINUTES} minuti, max: {self.MAX_MINUTES}\n"
                "Esempio: !kick Mario 60 spam"
            )

        user_identifier = args[0]

        # Parse minutes (optional, default 30)
        minutes = self.DEFAULT_MINUTES
        reason_start = 1

        if len(args) > 1 and args[1].isdigit():
            minutes = min(int(args[1]), self.MAX_MINUTES)
            reason_start = 2

        reason = " ".join(args[reason_start:]) if len(args) > reason_start else None

        # Find target user
        target = self.user_repo.find_user(user_identifier)

        if not target:
            return CommandResult.fail(
                f"[BBS] Utente '{user_identifier}' non trovato"
            )

        # Cannot kick yourself
        if target.public_key == ctx.sender_key:
            return CommandResult.fail("[BBS] Non puoi espellere te stesso")

        # Cannot kick admins
        if target.is_admin:
            return CommandResult.fail("[BBS] Non puoi espellere un admin")

        # Check if already banned
        if target.is_banned:
            return CommandResult.fail(
                f"[BBS] {target.display_name} è già bannato"
            )

        # Check if already kicked
        if target.is_kicked:
            remaining = target.kick_remaining_minutes
            return CommandResult.fail(
                f"[BBS] {target.display_name} è già espulso ({remaining} min rimanenti)"
            )

        # Perform kick
        self.user_repo.kick_user(target.public_key, minutes, reason)
        self.session.commit()

        reason_text = f" - Motivo: {reason}" if reason else ""
        return CommandResult.ok(
            f"[BBS] {target.display_name} espulso per {minutes} minuti{reason_text}"
        )


@CommandRegistry.register
class UnkickCommand(BaseCommand):
    """Remove kick from a user."""

    name = "unkick"
    description = "Rimuove l'espulsione da un utente"
    usage = "!unkick <utente>"
    aliases = []
    admin_only = True

    def __init__(self, session: Session):
        self.session = session
        self.user_repo = UserRepository(session)

    async def execute(
        self, ctx: CommandContext, args: List[str]
    ) -> CommandResult:
        """
        Execute the unkick command.

        Args:
            ctx: Command context
            args: [user_identifier]

        Returns:
            Result of the unkick operation
        """
        if not args:
            return CommandResult.fail(
                "[BBS] Uso: !unkick <utente>\n"
                "Esempio: !unkick Mario"
            )

        user_identifier = args[0]

        # Find target user
        target = self.user_repo.find_user(user_identifier)

        if not target:
            return CommandResult.fail(
                f"[BBS] Utente '{user_identifier}' non trovato"
            )

        # Check if not kicked
        if not target.is_kicked:
            return CommandResult.fail(
                f"[BBS] {target.display_name} non è espulso"
            )

        # Perform unkick
        self.user_repo.unkick_user(target.public_key)
        self.session.commit()

        return CommandResult.ok(
            f"[BBS] {target.display_name} può nuovamente accedere"
        )
