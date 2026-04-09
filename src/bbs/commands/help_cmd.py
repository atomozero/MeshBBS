"""
Help command for MeshCore BBS.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

from typing import List

from sqlalchemy.orm import Session

from .base import BaseCommand, CommandContext, CommandResult, CommandRegistry


@CommandRegistry.register
class HelpCommand(BaseCommand):
    """Display help information about available commands."""

    name = "help"
    description = "Mostra i comandi disponibili"
    usage = "!help [comando]"
    aliases = ["h", "?"]

    def __init__(self, session: Session):
        self.session = session

    async def execute(
        self, ctx: CommandContext, args: List[str]
    ) -> CommandResult:
        """
        Execute the help command.

        Without arguments: list all commands
        With argument: show help for specific command
        """
        if args:
            # Help for specific command
            cmd_name = args[0].lower().lstrip("!/")
            command_class = CommandRegistry.get(cmd_name)

            if command_class:
                command = command_class(self.session)
                if command.admin_only and not ctx.is_admin:
                    return CommandResult.fail(
                        f"[BBS] Comando '!{cmd_name}' riservato agli admin"
                    )
                return CommandResult.ok(
                    f"[BBS] !{command.name}: {command.description}\n"
                    f"Uso: {command.usage}"
                )
            else:
                return CommandResult.fail(
                    f"[BBS] Comando '!{cmd_name}' non trovato"
                )

        # List commands based on user role
        all_commands = CommandRegistry.get_public_commands()

        user_cmds = []
        admin_cmds = []
        for cmd in all_commands:
            if cmd.admin_only:
                admin_cmds.append(cmd)
            else:
                user_cmds.append(cmd)

        lines = ["[BBS] Comandi:"]
        lines.append(" ".join(sorted([f"!{c.name}" for c in user_cmds])))

        if ctx.is_admin and admin_cmds:
            lines.append("Admin:")
            lines.append(" ".join(sorted([f"!{c.name}" for c in admin_cmds])))

        lines.append("Usa !help <cmd> per dettagli")

        return CommandResult.ok("\n".join(lines))
