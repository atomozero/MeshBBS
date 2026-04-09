"""
Nodes command for MeshCore BBS.

Shows mesh network nodes and repeaters visible to the BBS.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

from typing import List

from sqlalchemy.orm import Session

from .base import BaseCommand, CommandContext, CommandResult, CommandRegistry


# Node type names from meshcore
NODE_TYPES = {0: "---", 1: "CLI", 2: "RPT", 3: "ROOM", 4: "SENS"}


@CommandRegistry.register
class NodesCommand(BaseCommand):
    """Show mesh network nodes visible to the BBS."""

    name = "nodes"
    description = "Mostra nodi e ripetitori sulla rete"
    usage = "!nodes"
    aliases = ["repeaters", "mesh"]

    def __init__(self, session: Session):
        self.session = session

    async def execute(
        self, ctx: CommandContext, args: List[str]
    ) -> CommandResult:
        """List visible mesh nodes."""
        try:
            from bbs.runtime import get_bbs_instance

            bbs = get_bbs_instance()
            if bbs is None or not bbs._running:
                return CommandResult.fail("[BBS] Servizio non attivo")

            mc = bbs.connection._meshcore
            if mc is None:
                return CommandResult.fail("[BBS] Radio non connessa")

            # Refresh contacts
            await mc.commands.get_contacts()
            contacts = mc.contacts

            if not contacts:
                return CommandResult.ok("[BBS] Nessun nodo visibile")

            lines = [f"[BBS] Nodi sulla rete ({len(contacts)}):"]

            for key, info in contacts.items():
                name = info.get("name", key[:8])
                node_type = NODE_TYPES.get(info.get("type", 0), "?")
                flags = info.get("flags", 0)
                path_str = ""

                # Show path/route info if available
                adv_name = info.get("adv_name", "")
                if adv_name:
                    path_str = f" via {adv_name}"

                marker = ""
                if node_type == "RPT":
                    marker = " [R]"
                elif node_type == "ROOM":
                    marker = " [B]"

                lines.append(f"  {name}{marker}{path_str}")

            return CommandResult.ok("\n".join(lines))

        except ImportError:
            return CommandResult.fail("[BBS] Comando non disponibile")
        except Exception as e:
            return CommandResult.fail(f"[BBS] Errore: {e}")
