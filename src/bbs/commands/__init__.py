"""Command system for MeshCore BBS."""

from .base import BaseCommand, CommandContext, CommandResult, CommandRegistry
from .parser import parse_command, ParsedCommand
from .dispatcher import CommandDispatcher

# Import all command modules so @CommandRegistry.register decorators execute
from . import (  # noqa: F401
    advert_cmd,
    board_cmd,
    delete_cmd,
    fortune_cmd,
    help_cmd,
    list_cmd,
    mail_cmd,
    meteo_cmd,
    news_cmd,
    nodes_cmd,
    ping_cmd,
    trivia_cmd,
    post_cmd,
    read_cmd,
    areas_cmd,
    nick_cmd,
    msg_cmd,
    inbox_cmd,
    readpm_cmd,
    reply_cmd,
    search_cmd,
    who_cmd,
    admin_cmd,
    area_admin_cmd,
    utility_cmd,
    privacy_cmd,
)

__all__ = [
    "BaseCommand",
    "CommandContext",
    "CommandResult",
    "CommandRegistry",
    "parse_command",
    "ParsedCommand",
    "CommandDispatcher",
]
