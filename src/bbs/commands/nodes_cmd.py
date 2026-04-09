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
    admin_only = True

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

            # Collect repeater names for path resolution
            repeaters = {}
            for k, info in contacts.items():
                if info.get("type") == 2:  # RPT
                    pk = info.get("public_key", k)
                    if isinstance(pk, bytes):
                        pk = pk.hex()
                    rname = info.get("adv_name", "") or info.get("name", pk[:8])
                    repeaters[pk[:8]] = rname

            rpt_count = len(repeaters)
            cli_count = sum(1 for i in contacts.values() if i.get("type") == 1)

            lines = [f"[BBS] Rete: {len(contacts)} nodi ({rpt_count} RPT, {cli_count} CLI)"]

            for key, info in contacts.items():
                name = info.get("adv_name", "") or info.get("name", key[:8])
                node_type = NODE_TYPES.get(info.get("type", 0), "?")
                out_path_len = info.get("out_path_len", 0)

                marker = ""
                if node_type == "RPT":
                    marker = "[R]"
                elif node_type == "ROOM":
                    marker = "[B]"
                elif node_type == "SENS":
                    marker = "[S]"

                hop_str = f" {out_path_len}h" if out_path_len and out_path_len > 0 else ""
                lines.append(f"  {marker}{name}{hop_str}")

            return CommandResult.ok("\n".join(lines))

        except ImportError:
            return CommandResult.fail("[BBS] Comando non disponibile")
        except Exception as e:
            return CommandResult.fail(f"[BBS] Errore: {e}")
