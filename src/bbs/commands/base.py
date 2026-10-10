"""
Base classes for the command system.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Tuple, Type

# Package holding the built-in command modules (e.g. "bbs.commands")
_BUILTIN_PACKAGE = __name__.rsplit(".", 1)[0]


@dataclass
class CommandContext:
    """
    Context information passed to command handlers.

    Contains all information about the incoming message and sender.
    """

    sender_key: str
    sender_name: Optional[str]
    raw_message: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    hops: int = 0
    rssi: Optional[int] = None
    is_admin: bool = False
    is_moderator: bool = False

    @property
    def sender_display(self) -> str:
        """Get display name for sender."""
        return self.sender_name or self.sender_key[:8]


@dataclass
class CommandResult:
    """
    Result of command execution.

    Contains the response to send back and execution status.
    """

    success: bool
    response: str
    error: Optional[str] = None

    @classmethod
    def ok(cls, response: str) -> "CommandResult":
        """Create a successful result."""
        return cls(success=True, response=response)

    @classmethod
    def fail(cls, response: str, error: Optional[str] = None) -> "CommandResult":
        """Create a failed result."""
        return cls(success=False, response=response, error=error)


class BaseCommand(ABC):
    """
    Abstract base class for all BBS commands.

    Subclass this and implement execute() to create new commands.
    """

    # Command metadata - override in subclasses
    name: str = ""
    description: str = ""
    usage: str = ""
    aliases: List[str] = []
    admin_only: bool = False
    hidden: bool = False

    @abstractmethod
    async def execute(
        self, ctx: CommandContext, args: List[str]
    ) -> CommandResult:
        """
        Execute the command.

        Args:
            ctx: Command context with sender info
            args: List of command arguments

        Returns:
            CommandResult with response
        """
        pass

    def get_help(self) -> str:
        """Get help text for this command."""
        return f"!{self.name}: {self.description}\nUso: {self.usage}"


class CommandRegistry:
    """
    Registry for all available commands.

    Provides command lookup by name or alias.
    """

    _commands: Dict[str, Type[BaseCommand]] = {}
    _aliases: Dict[str, str] = {}  # alias -> command name
    # Every built-in command class (defined in the bbs.commands package) ever
    # registered. Not affected by clear(), so built-ins can be restored after
    # a clear() even though their modules are already imported (registration
    # happens at import time and would not run again).
    _builtins: List[Type[BaseCommand]] = []

    @classmethod
    def register(cls, command_class: Type[BaseCommand]) -> Type[BaseCommand]:
        """
        Register a command class.

        Can be used as a decorator:
            @CommandRegistry.register
            class MyCommand(BaseCommand):
                ...

        Args:
            command_class: Command class to register

        Returns:
            The command class (for decorator usage)
        """
        name = command_class.name.lower()
        cls._commands[name] = command_class

        if (
            command_class.__module__.startswith(_BUILTIN_PACKAGE + ".")
            and command_class not in cls._builtins
        ):
            cls._builtins.append(command_class)

        # Register aliases
        for alias in command_class.aliases:
            cls._aliases[alias.lower()] = name

        return command_class

    @classmethod
    def get(cls, name: str) -> Optional[Type[BaseCommand]]:
        """
        Get a command class by name or alias.

        Args:
            name: Command name or alias

        Returns:
            Command class or None
        """
        name = name.lower()

        # Check direct match
        if name in cls._commands:
            return cls._commands[name]

        # Check aliases
        if name in cls._aliases:
            return cls._commands[cls._aliases[name]]

        return None

    @classmethod
    def get_all(cls) -> List[Type[BaseCommand]]:
        """Get all registered commands."""
        return list(cls._commands.values())

    @classmethod
    def get_public_commands(cls) -> List[Type[BaseCommand]]:
        """Get all non-hidden commands."""
        return [cmd for cmd in cls._commands.values() if not cmd.hidden]

    @classmethod
    def get_command_names(cls) -> List[str]:
        """Get all command names."""
        return list(cls._commands.keys())

    @classmethod
    def unregister(cls, command_class: Type[BaseCommand]) -> bool:
        """
        Remove a command class (and its aliases) from the registry.

        Only removes the entry if it currently maps to this exact class, so
        unregistering a plugin command never removes a different command
        registered under the same name.

        Returns:
            True if the command was removed
        """
        name = command_class.name.lower()
        if cls._commands.get(name) is not command_class:
            return False
        del cls._commands[name]
        for alias, target in list(cls._aliases.items()):
            if target == name:
                del cls._aliases[alias]
        return True

    @classmethod
    def ensure_builtins(cls) -> None:
        """
        Re-register built-in commands that are missing from the registry
        (e.g. after clear()). Commands already registered under the same
        name (such as plugin overrides) are left untouched.
        """
        for command_class in list(cls._builtins):
            name = command_class.name.lower()
            if name not in cls._commands:
                cls._commands[name] = command_class
            for alias in command_class.aliases:
                cls._aliases.setdefault(alias.lower(), name)

    @classmethod
    def snapshot(cls) -> Tuple[Dict[str, Type[BaseCommand]], Dict[str, str]]:
        """Return a copy of the registry state (for testing)."""
        return dict(cls._commands), dict(cls._aliases)

    @classmethod
    def restore(
        cls, state: Tuple[Dict[str, Type[BaseCommand]], Dict[str, str]]
    ) -> None:
        """Restore a registry state previously returned by snapshot()."""
        commands, aliases = state
        cls._commands.clear()
        cls._commands.update(commands)
        cls._aliases.clear()
        cls._aliases.update(aliases)

    @classmethod
    def clear(cls) -> None:
        """Clear all registered commands (for testing)."""
        cls._commands.clear()
        cls._aliases.clear()
