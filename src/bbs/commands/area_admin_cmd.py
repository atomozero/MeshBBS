"""
Area administration commands for MeshCore BBS.

Commands for managing areas: newarea, delarea, editarea.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

import re
from typing import List

from sqlalchemy.orm import Session

from .base import BaseCommand, CommandContext, CommandResult, CommandRegistry
from bbs.repositories.area_repository import AreaRepository


@CommandRegistry.register
class NewAreaCommand(BaseCommand):
    """Create a new discussion area."""

    name = "newarea"
    description = "Crea una nuova area"
    usage = "!newarea <nome> [descrizione]"
    aliases = ["createarea", "addarea"]
    admin_only = True

    # Area name constraints
    MIN_NAME_LENGTH = 2
    MAX_NAME_LENGTH = 32
    NAME_PATTERN = re.compile(r"^[a-zA-Z][a-zA-Z0-9_-]*$")

    def __init__(self, session: Session):
        self.session = session
        self.area_repo = AreaRepository(session)

    async def execute(
        self, ctx: CommandContext, args: List[str]
    ) -> CommandResult:
        """
        Execute the newarea command.

        Args:
            ctx: Command context
            args: [area_name, ...description]

        Returns:
            Result of the area creation
        """
        if not args:
            return CommandResult.fail(
                "[BBS] Uso: !newarea <nome> [descrizione]\n"
                "Esempio: !newarea gaming Discussioni sui videogiochi\n"
                f"Nome: {self.MIN_NAME_LENGTH}-{self.MAX_NAME_LENGTH} caratteri, lettere/numeri"
            )

        area_name = args[0].lower().lstrip("#")
        description = " ".join(args[1:]) if len(args) > 1 else None

        # Validate name length
        if len(area_name) < self.MIN_NAME_LENGTH:
            return CommandResult.fail(
                f"[BBS] Nome troppo corto (min {self.MIN_NAME_LENGTH} caratteri)"
            )

        if len(area_name) > self.MAX_NAME_LENGTH:
            return CommandResult.fail(
                f"[BBS] Nome troppo lungo (max {self.MAX_NAME_LENGTH} caratteri)"
            )

        # Validate name format
        if not self.NAME_PATTERN.match(area_name):
            return CommandResult.fail(
                "[BBS] Nome non valido. Usa solo lettere, numeri, - e _\n"
                "Deve iniziare con una lettera"
            )

        # Check if area already exists
        existing = self.area_repo.get_by_name(area_name)
        if existing:
            return CommandResult.fail(
                f"[BBS] L'area '{area_name}' esiste già"
            )

        # Create area
        area = self.area_repo.create_area(
            name=area_name,
            description=description,
            created_by=ctx.sender_key,
        )
        self.session.commit()

        desc_text = f" - {description}" if description else ""
        return CommandResult.ok(
            f"[BBS] Area #{area_name} creata{desc_text}"
        )


@CommandRegistry.register
class DelAreaCommand(BaseCommand):
    """Delete a discussion area."""

    name = "delarea"
    description = "Elimina un'area"
    usage = "!delarea <nome>"
    aliases = ["deletearea", "rmarea"]
    admin_only = True

    # Protected areas that cannot be deleted
    PROTECTED_AREAS = ["generale", "general"]

    def __init__(self, session: Session):
        self.session = session
        self.area_repo = AreaRepository(session)

    async def execute(
        self, ctx: CommandContext, args: List[str]
    ) -> CommandResult:
        """
        Execute the delarea command.

        Args:
            ctx: Command context
            args: [area_name]

        Returns:
            Result of the area deletion
        """
        if not args:
            return CommandResult.fail(
                "[BBS] Uso: !delarea <nome>\n"
                "Esempio: !delarea test\n"
                "ATTENZIONE: Elimina anche tutti i messaggi!"
            )

        area_name = args[0].lower().lstrip("#")

        # Check if area exists
        area = self.area_repo.get_by_name(area_name)
        if not area:
            return CommandResult.fail(
                f"[BBS] Area '{area_name}' non trovata"
            )

        # Check if protected
        if area_name.lower() in self.PROTECTED_AREAS:
            return CommandResult.fail(
                f"[BBS] L'area '{area_name}' è protetta e non può essere eliminata"
            )

        # Get message count for warning
        msg_count = area.message_count

        # Delete area
        self.area_repo.delete_area(area_name, deleted_by=ctx.sender_key)
        self.session.commit()

        if msg_count > 0:
            return CommandResult.ok(
                f"[BBS] Area #{area_name} eliminata ({msg_count} messaggi rimossi)"
            )
        else:
            return CommandResult.ok(
                f"[BBS] Area #{area_name} eliminata"
            )


@CommandRegistry.register
class EditAreaCommand(BaseCommand):
    """Edit an area's properties."""

    name = "editarea"
    description = "Modifica un'area"
    usage = "!editarea <nome> <proprietà> <valore>"
    aliases = ["modarea"]
    admin_only = True

    def __init__(self, session: Session):
        self.session = session
        self.area_repo = AreaRepository(session)

    async def execute(
        self, ctx: CommandContext, args: List[str]
    ) -> CommandResult:
        """
        Execute the editarea command.

        Args:
            ctx: Command context
            args: [area_name, property, value...]

        Returns:
            Result of the area modification
        """
        if len(args) < 2:
            return CommandResult.fail(
                "[BBS] Uso: !editarea <nome> <proprietà> [valore]\n"
                "Proprietà:\n"
                "  desc <testo> - Cambia descrizione\n"
                "  readonly on/off - Imposta sola lettura\n"
                "  public on/off - Imposta visibilità\n"
                "Esempio: !editarea tech desc Area per discussioni tecniche"
            )

        area_name = args[0].lower().lstrip("#")
        prop = args[1].lower()
        value = " ".join(args[2:]) if len(args) > 2 else None

        # Check if area exists
        area = self.area_repo.get_by_name(area_name)
        if not area:
            return CommandResult.fail(
                f"[BBS] Area '{area_name}' non trovata"
            )

        # Handle different properties
        if prop in ["desc", "description", "descrizione"]:
            if not value:
                return CommandResult.fail(
                    "[BBS] Specifica la nuova descrizione"
                )

            self.area_repo.update_area(
                name=area_name,
                new_description=value,
                modified_by=ctx.sender_key,
            )
            self.session.commit()

            return CommandResult.ok(
                f"[BBS] Descrizione di #{area_name} aggiornata"
            )

        elif prop in ["readonly", "ro", "sololettura"]:
            if value is None or value.lower() not in ["on", "off", "true", "false", "1", "0"]:
                return CommandResult.fail(
                    "[BBS] Usa: !editarea <nome> readonly on/off"
                )

            new_readonly = value.lower() in ["on", "true", "1"]

            self.area_repo.update_area(
                name=area_name,
                new_readonly=new_readonly,
                modified_by=ctx.sender_key,
            )
            self.session.commit()

            status = "sola lettura" if new_readonly else "scrittura abilitata"
            return CommandResult.ok(
                f"[BBS] #{area_name} ora è in modalità {status}"
            )

        elif prop in ["public", "pubblica", "visibile"]:
            if value is None or value.lower() not in ["on", "off", "true", "false", "1", "0"]:
                return CommandResult.fail(
                    "[BBS] Usa: !editarea <nome> public on/off"
                )

            new_public = value.lower() in ["on", "true", "1"]

            self.area_repo.update_area(
                name=area_name,
                new_public=new_public,
                modified_by=ctx.sender_key,
            )
            self.session.commit()

            status = "pubblica" if new_public else "nascosta"
            return CommandResult.ok(
                f"[BBS] #{area_name} ora è {status}"
            )

        else:
            return CommandResult.fail(
                f"[BBS] Proprietà '{prop}' sconosciuta\n"
                "Usa: desc, readonly, public"
            )


@CommandRegistry.register
class ListAreasAdminCommand(BaseCommand):
    """List all areas with admin details."""

    name = "listareas"
    description = "Lista tutte le aree (admin)"
    usage = "!listareas"
    aliases = []
    admin_only = True

    def __init__(self, session: Session):
        self.session = session
        self.area_repo = AreaRepository(session)

    async def execute(
        self, ctx: CommandContext, args: List[str]
    ) -> CommandResult:
        """
        Execute the listareas command.

        Args:
            ctx: Command context
            args: Not used

        Returns:
            List of all areas with details
        """
        areas = self.area_repo.get_all_areas()

        if not areas:
            return CommandResult.ok("[BBS] Nessuna area configurata")

        lines = ["[BBS] Aree (admin view):"]

        for area in areas:
            flags = []
            if area.is_readonly:
                flags.append("RO")
            if not area.is_public:
                flags.append("HIDDEN")

            flag_str = f" [{','.join(flags)}]" if flags else ""
            desc = f" - {area.description}" if area.description else ""

            lines.append(f"  #{area.name}{flag_str}: {area.message_count} msg{desc}")

        lines.append(f"Totale: {len(areas)} aree")

        return CommandResult.ok("\n".join(lines))
