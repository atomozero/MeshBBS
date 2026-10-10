"""
Help command for MeshCore BBS.

!help            -> essential commands + list of categories
!help <categoria> -> commands of that category (compact, names only)
!help tutti      -> every command available to the sender
!help <comando>  -> description and usage of a command

Output is kept short: every line costs airtime on LoRa.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

from typing import List, Optional

from sqlalchemy.orm import Session

from .base import BaseCommand, CommandContext, CommandResult, CommandRegistry

# Category -> command names (canonical names). Names not registered are
# skipped, so plugins/optional commands don't break the listing.
# Category keys must not collide with command names or aliases.
CATEGORIES = {
    "forum": ["post", "read", "list", "areas", "reply", "search", "delete", "board"],
    "posta": [
        "msg", "msg!", "inbox", "readpm", "delpm", "clear",
        "mail", "mailbox", "readmail", "delmail",
    ],
    "utili": [
        "who", "whois", "nick", "staff", "stats", "info", "ping",
        "news", "meteo", "notifiche", "gdpr", "mydata",
    ],
    "giochi": ["trivia", "fortune"],
    "mod": [
        "kick", "unkick", "mute", "unmute",
        "ban", "unban", "promote", "demote",
        "newarea", "delarea", "editarea", "listareas",
        "cleanup", "nodes", "advert",
    ],
}
CATEGORY_ALIASES = {
    "messaggi": "posta",
    "games": "giochi",
    "moderazione": "mod",
}
ALL_KEYWORDS = {"tutti", "all"}

ESSENTIAL = ["post", "read", "list", "areas", "msg", "inbox", "who", "nick"]


def _can_use(command_class, ctx: CommandContext) -> bool:
    """Same permission rule as the dispatcher."""
    if not command_class.admin_only:
        return True
    if ctx.is_admin:
        return True
    return bool(getattr(command_class, "moderator_allowed", False) and ctx.is_moderator)


@CommandRegistry.register
class HelpCommand(BaseCommand):
    """Display help information about available commands."""

    name = "help"
    description = "Mostra i comandi disponibili"
    usage = "!help [comando|categoria|tutti]"
    aliases = ["h", "?"]

    def __init__(self, session: Session):
        self.session = session

    def _available(self, names: List[str], ctx: CommandContext) -> List[str]:
        result = []
        for n in names:
            cls = CommandRegistry.get(n)
            if cls is not None and cls.name == n and not cls.hidden and _can_use(cls, ctx):
                result.append(n)
        return result

    def _categories_for(self, ctx: CommandContext) -> List[str]:
        return [c for c in CATEGORIES if self._available(CATEGORIES[c], ctx)]

    def _resolve_category(self, word: str) -> Optional[str]:
        if word in CATEGORIES:
            return word
        return CATEGORY_ALIASES.get(word)

    async def execute(
        self, ctx: CommandContext, args: List[str]
    ) -> CommandResult:
        """
        Execute the help command.

        Without arguments: essential commands and categories
        With argument: category listing, full listing or command help
        """
        if args:
            word = args[0].lower().lstrip("!/")

            if word in ALL_KEYWORDS:
                names = sorted(
                    cls.name for cls in CommandRegistry.get_public_commands()
                    if _can_use(cls, ctx)
                )
                return CommandResult.ok(
                    "[BBS] Comandi: " + " ".join(names) + "\n!help <cmd> per dettagli"
                )

            category = self._resolve_category(word)
            if category:
                names = self._available(CATEGORIES[category], ctx)
                if not names:
                    return CommandResult.fail(
                        f"[BBS] Categoria '{word}' non disponibile"
                    )
                return CommandResult.ok(
                    f"[BBS] {category}: " + " ".join(f"!{n}" for n in names)
                )

            # Help for specific command
            command_class = CommandRegistry.get(word)

            if command_class and not command_class.hidden:
                command = command_class(self.session)
                if not _can_use(command_class, ctx):
                    return CommandResult.fail(
                        f"[BBS] Comando '!{word}' riservato agli admin"
                    )
                return CommandResult.ok(
                    f"[BBS] !{command.name}: {command.description}\n"
                    f"Uso: {command.usage}"
                )
            return CommandResult.fail(
                f"[BBS] Comando '!{word}' non trovato. !help tutti"
            )

        # Short list of essential commands + categories: must stay within
        # ~2 mesh chunks. The rest is discoverable via categories.
        essential = self._available(ESSENTIAL, ctx)
        categories = self._categories_for(ctx)
        response = (
            "[BBS] Comandi: " + " ".join(f"!{n}" for n in essential) + "\n"
            "Categorie: !help " + "|".join(categories) + "|tutti\n"
            "!help <cmd> per dettagli"
        )
        return CommandResult.ok(response)
