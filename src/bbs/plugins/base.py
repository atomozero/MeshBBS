"""
Base classes for MeshBBS plugins.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any, Type

from ..commands.base import BaseCommand


class PluginState(str, Enum):
    """Plugin lifecycle states."""
    UNLOADED = "unloaded"
    LOADING = "loading"
    LOADED = "loaded"
    ENABLED = "enabled"
    DISABLED = "disabled"
    ERROR = "error"


@dataclass
class PluginInfo:
    """
    Metadata about a plugin.

    This information is displayed to admins and used for plugin management.
    """

    name: str
    version: str
    description: str
    author: str
    min_bbs_version: str = "1.0.0"
    dependencies: List[str] = field(default_factory=list)
    homepage: Optional[str] = None
    license: str = "MIT"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "min_bbs_version": self.min_bbs_version,
            "dependencies": self.dependencies,
            "homepage": self.homepage,
            "license": self.license,
        }


class BasePlugin(ABC):
    """
    Abstract base class for MeshBBS plugins.

    Plugins can provide custom commands, hooks, and functionality.

    Example usage:
        class MyPlugin(BasePlugin):
            @property
            def info(self) -> PluginInfo:
                return PluginInfo(
                    name="my-plugin",
                    version="1.0.0",
                    description="My awesome plugin",
                    author="Your Name"
                )

            def get_commands(self) -> List[Type[BaseCommand]]:
                return [MyCustomCommand]

            async def on_load(self) -> bool:
                # Setup code
                return True

            async def on_unload(self) -> None:
                # Cleanup code
                pass
    """

    def __init__(self):
        """Initialize the plugin."""
        self._state = PluginState.UNLOADED
        self._loaded_at: Optional[datetime] = None
        self._error: Optional[str] = None
        self._config: Dict[str, Any] = {}

    @property
    @abstractmethod
    def info(self) -> PluginInfo:
        """
        Get plugin metadata.

        Returns:
            PluginInfo with plugin details
        """
        pass

    @property
    def state(self) -> PluginState:
        """Get current plugin state."""
        return self._state

    @property
    def error(self) -> Optional[str]:
        """Get last error message."""
        return self._error

    @property
    def config(self) -> Dict[str, Any]:
        """Get plugin configuration."""
        return self._config

    def set_config(self, config: Dict[str, Any]) -> None:
        """
        Set plugin configuration.

        Args:
            config: Configuration dictionary
        """
        self._config = config

    def get_commands(self) -> List[Type[BaseCommand]]:
        """
        Get commands provided by this plugin.

        Override this to register custom commands.

        Returns:
            List of BaseCommand subclasses
        """
        return []

    async def on_load(self) -> bool:
        """
        Called when the plugin is loaded.

        Override to perform initialization. Return False to indicate failure.

        Returns:
            True if loaded successfully, False otherwise
        """
        return True

    async def on_unload(self) -> None:
        """
        Called when the plugin is unloaded.

        Override to perform cleanup.
        """
        pass

    async def on_enable(self) -> bool:
        """
        Called when the plugin is enabled.

        Override for enable-specific logic.

        Returns:
            True if enabled successfully, False otherwise
        """
        return True

    async def on_disable(self) -> None:
        """
        Called when the plugin is disabled.

        Override for disable-specific logic.
        """
        pass

    async def on_message(
        self,
        sender_key: str,
        message: str,
        is_command: bool,
    ) -> Optional[str]:
        """
        Hook called for every incoming message.

        Can be used for logging, filtering, or custom processing.

        Args:
            sender_key: Sender's public key
            message: Message text
            is_command: True if message is a BBS command

        Returns:
            Optional response to inject, or None
        """
        return None

    async def on_command(
        self,
        command: str,
        args: List[str],
        sender_key: str,
    ) -> Optional[str]:
        """
        Hook called before command execution.

        Can be used to intercept or modify commands.

        Args:
            command: Command name
            args: Command arguments
            sender_key: Sender's public key

        Returns:
            Response to return instead of executing command, or None
        """
        return None

    async def on_user_join(self, user_key: str, nickname: Optional[str]) -> None:
        """
        Hook called when a new user joins.

        Args:
            user_key: User's public key
            nickname: User's nickname if set
        """
        pass

    async def on_user_leave(self, user_key: str) -> None:
        """
        Hook called when a user leaves (timeout/disconnect).

        Args:
            user_key: User's public key
        """
        pass

    def get_status(self) -> Dict[str, Any]:
        """
        Get plugin status.

        Returns:
            Dictionary with plugin status information
        """
        return {
            "name": self.info.name,
            "version": self.info.version,
            "state": self._state.value,
            "loaded_at": self._loaded_at.isoformat() if self._loaded_at else None,
            "error": self._error,
            "commands": [cmd.name for cmd in self.get_commands()],
        }

    def __repr__(self) -> str:
        return f"<Plugin {self.info.name} v{self.info.version} [{self._state.value}]>"
