"""
Command parser for MeshCore BBS.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

from dataclasses import dataclass
from typing import Optional, List
import re


@dataclass
class ParsedCommand:
    """
    Result of parsing a command message.

    Contains the extracted command name and arguments.
    """

    command: str  # Command name without /
    args: List[str]  # Arguments as list
    raw_args: str  # Arguments as single string
    is_valid: bool = True

    @property
    def has_args(self) -> bool:
        """Check if command has any arguments."""
        return len(self.args) > 0

    def get_arg(self, index: int, default: str = "") -> str:
        """
        Get argument at index safely.

        Args:
            index: Argument index
            default: Default value if not found

        Returns:
            Argument value or default
        """
        if 0 <= index < len(self.args):
            return self.args[index]
        return default


def parse_command(message: str) -> Optional[ParsedCommand]:
    """
    Parse a message to extract command and arguments.

    Commands must start with / followed by the command name.
    Arguments are space-separated, but quoted strings are kept together.

    Args:
        message: Raw message text

    Returns:
        ParsedCommand if message is a command, None otherwise

    Examples:
        >>> parse_command("/help")
        ParsedCommand(command='help', args=[], raw_args='')

        >>> parse_command("/post Hello world!")
        ParsedCommand(command='post', args=['Hello', 'world!'], raw_args='Hello world!')

        >>> parse_command("Hello")
        None
    """
    if not message:
        return None

    message = message.strip()

    # Commands must start with /
    if not message.startswith("/"):
        return None

    # Remove leading /
    message = message[1:]

    if not message:
        return None

    # Split command and arguments
    parts = message.split(maxsplit=1)
    command = parts[0].lower()

    # Validate command name (alphanumeric, underscore, and ! for ephemeral commands)
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9_]*!?$", command):
        return ParsedCommand(
            command=command,
            args=[],
            raw_args="",
            is_valid=False,
        )

    # Parse arguments
    raw_args = parts[1] if len(parts) > 1 else ""
    args = _parse_args(raw_args)

    return ParsedCommand(
        command=command,
        args=args,
        raw_args=raw_args,
        is_valid=True,
    )


def _parse_args(args_string: str) -> List[str]:
    """
    Parse argument string into list.

    Handles quoted strings as single arguments.

    Args:
        args_string: Raw arguments string

    Returns:
        List of arguments
    """
    if not args_string:
        return []

    args = []
    current = ""
    in_quotes = False
    quote_char = None

    for char in args_string:
        if char in ('"', "'") and not in_quotes:
            in_quotes = True
            quote_char = char
        elif char == quote_char and in_quotes:
            in_quotes = False
            quote_char = None
            if current:
                args.append(current)
                current = ""
        elif char == " " and not in_quotes:
            if current:
                args.append(current)
                current = ""
        else:
            current += char

    # Don't forget the last argument
    if current:
        args.append(current)

    return args


def is_command(message: str) -> bool:
    """
    Quick check if a message is a command.

    Args:
        message: Message to check

    Returns:
        True if message starts with /
    """
    return bool(message and message.strip().startswith("/"))
