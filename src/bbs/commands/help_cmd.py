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
            cmd_name = args[0].lower().lstrip("/")
            command_class = CommandRegistry.get(cmd_name)

            if command_class:
                command = command_class(self.session)
                return CommandResult.ok(
                    f"[BBS] /{command.name}: {command.description}\n"
                    f"Uso: {command.usage}"
                )
            else:
                return CommandResult.fail(
                    f"[BBS] Comando '/{cmd_name}' non trovato"
                )

        # List all commands
        commands = CommandRegistry.get_public_commands()
        cmd_list = " ".join(sorted([f"/{cmd.name}" for cmd in commands]))

        return CommandResult.ok(
            f"[BBS] Comandi: {cmd_list}\n"
            f"Usa !help <cmd> per dettagli"
        )
