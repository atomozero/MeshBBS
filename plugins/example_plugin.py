"""
Example plugin for MeshBBS.

This is a sample plugin that demonstrates how to create custom
commands and hooks for MeshBBS.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

from datetime import datetime
from typing import List, Optional, Type

# Add src to path for development
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from bbs.plugins.base import BasePlugin, PluginInfo
from bbs.commands.base import BaseCommand, CommandContext, CommandResult


class PingCommand(BaseCommand):
    """Simple ping command to test responsiveness."""

    name = "ping"
    description = "Test BBS responsiveness"
    usage = "/ping"
    aliases = ["pong"]
    admin_only = False

    def __init__(self, session=None):
        self.session = session

    async def execute(
        self, ctx: CommandContext, args: List[str]
    ) -> CommandResult:
        latency = f" (hops: {ctx.hops})" if ctx.hops > 0 else ""
        return CommandResult.ok(f"Pong!{latency}")


class UptimeCommand(BaseCommand):
    """Show plugin uptime."""

    name = "pluginup"
    description = "Show plugin uptime"
    usage = "/pluginup"
    aliases = []
    admin_only = False

    # Class-level start time (set when plugin loads)
    _start_time: Optional[datetime] = None

    def __init__(self, session=None):
        self.session = session

    async def execute(
        self, ctx: CommandContext, args: List[str]
    ) -> CommandResult:
        if not self._start_time:
            return CommandResult.ok("Plugin start time not set")

        delta = datetime.utcnow() - self._start_time
        hours = int(delta.total_seconds() // 3600)
        minutes = int((delta.total_seconds() % 3600) // 60)
        seconds = int(delta.total_seconds() % 60)

        return CommandResult.ok(f"Plugin uptime: {hours}h {minutes}m {seconds}s")


class EchoCommand(BaseCommand):
    """Echo back the provided text."""

    name = "echo"
    description = "Echo back text"
    usage = "/echo <text>"
    aliases = []
    admin_only = False

    def __init__(self, session=None):
        self.session = session

    async def execute(
        self, ctx: CommandContext, args: List[str]
    ) -> CommandResult:
        if not args:
            return CommandResult.fail("Uso: /echo <text>")
        return CommandResult.ok(" ".join(args))


class ExamplePlugin(BasePlugin):
    """
    Example plugin demonstrating custom commands and hooks.

    This plugin provides:
    - /ping: Test BBS responsiveness
    - /pluginup: Show plugin uptime
    - /echo: Echo back text

    And hooks:
    - Logs all incoming messages
    - Welcomes new users
    """

    @property
    def info(self) -> PluginInfo:
        return PluginInfo(
            name="example-plugin",
            version="1.0.0",
            description="Example plugin with sample commands",
            author="MeshBBS Team",
            min_bbs_version="1.0.0",
            homepage="https://github.com/meshbbs/example-plugin",
        )

    def get_commands(self) -> List[Type[BaseCommand]]:
        return [PingCommand, UptimeCommand, EchoCommand]

    async def on_load(self) -> bool:
        """Initialize plugin."""
        UptimeCommand._start_time = datetime.utcnow()
        print(f"[{self.info.name}] Plugin loaded!")
        return True

    async def on_unload(self) -> None:
        """Cleanup plugin."""
        print(f"[{self.info.name}] Plugin unloaded!")

    async def on_enable(self) -> bool:
        """Enable plugin."""
        print(f"[{self.info.name}] Plugin enabled!")
        return True

    async def on_disable(self) -> None:
        """Disable plugin."""
        print(f"[{self.info.name}] Plugin disabled!")

    async def on_message(
        self,
        sender_key: str,
        message: str,
        is_command: bool,
    ) -> Optional[str]:
        """Log all messages."""
        msg_type = "CMD" if is_command else "MSG"
        print(f"[{self.info.name}] {msg_type} from {sender_key[:8]}: {message[:50]}")
        return None

    async def on_user_join(
        self,
        user_key: str,
        nickname: Optional[str],
    ) -> None:
        """Welcome new users."""
        name = nickname or user_key[:8]
        print(f"[{self.info.name}] Welcome {name}!")


# Export the plugin class
Plugin = ExamplePlugin
