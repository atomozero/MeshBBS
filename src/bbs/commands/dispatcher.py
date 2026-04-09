"""
Command dispatcher for MeshCore BBS.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from .base import CommandContext, CommandResult, CommandRegistry
from .parser import parse_command, is_command
from bbs.repositories.user_repository import UserRepository
from bbs.rate_limiter import RateLimiter

try:
    from utils.logger import get_logger
    logger = get_logger("meshbbs.commands")
except ImportError:
    import logging
    logger = logging.getLogger("meshbbs.commands")


class CommandDispatcher:
    """
    Dispatches incoming messages to appropriate command handlers.

    Handles command parsing, permission checking, rate limiting, and execution.
    """

    def __init__(
        self,
        session: Session,
        response_prefix: str = "[BBS]",
        rate_limiter: Optional[RateLimiter] = None,
    ):
        """
        Initialize the dispatcher.

        Args:
            session: Database session
            response_prefix: Prefix for all BBS responses
            rate_limiter: Optional rate limiter instance
        """
        self.session = session
        self.response_prefix = response_prefix
        self.user_repo = UserRepository(session)
        self.rate_limiter = rate_limiter

        # Import and register commands
        self._register_default_commands()

    def _register_default_commands(self) -> None:
        """Register all default commands."""
        # Import here to avoid circular imports
        from . import help_cmd, post_cmd, list_cmd, read_cmd, areas_cmd, nick_cmd, who_cmd
        from . import msg_cmd, inbox_cmd, readpm_cmd, reply_cmd, search_cmd, admin_cmd
        from . import area_admin_cmd, utility_cmd, privacy_cmd

        # Commands are auto-registered via decorator

    async def dispatch(
        self,
        message: str,
        sender_key: str,
        hops: int = 0,
        rssi: Optional[int] = None,
    ) -> Optional[str]:
        """
        Process a message and return response if it's a command.

        Args:
            message: Raw message text
            sender_key: Sender's public key
            hops: Number of hops from MeshCore
            rssi: Signal strength

        Returns:
            Response string or None if not a command
        """
        # Check if it's a command
        if not is_command(message):
            return None

        # Parse the command
        parsed = parse_command(message)

        if not parsed:
            return None

        if not parsed.is_valid:
            return self._format_response("Comando non valido")

        # Get or create user
        user, is_new = self.user_repo.get_or_create(sender_key)

        if is_new:
            logger.info(f"New user: {sender_key[:8]}...")

        # Check if user is banned or kicked
        if not user.is_active():
            if user.is_banned:
                logger.warning(f"Banned user attempted command: {sender_key[:8]}")
            else:
                logger.warning(f"Kicked user attempted command: {sender_key[:8]}")
            return self._format_response("Accesso negato")

        # Check rate limiting
        if self.rate_limiter:
            # Admins bypass rate limiting
            if user.is_admin:
                self.rate_limiter.add_to_whitelist(sender_key)

            allowed, error_msg = self.rate_limiter.check(sender_key)
            if not allowed:
                logger.warning(f"Rate limited: {sender_key[:8]} - {error_msg}")
                return self._format_response(error_msg)

        # Create context
        ctx = CommandContext(
            sender_key=sender_key,
            sender_name=user.nickname,
            raw_message=message,
            timestamp=datetime.utcnow(),
            hops=hops,
            rssi=rssi,
        )

        # Get command handler
        command_class = CommandRegistry.get(parsed.command)

        if not command_class:
            logger.debug(f"Unknown command: /{parsed.command}")
            return self._format_response(
                f"Comando '/{parsed.command}' sconosciuto. Usa /help"
            )

        # Check admin permission
        command = command_class(self.session)
        if command.admin_only and not user.is_admin:
            logger.warning(
                f"Non-admin {sender_key[:8]} attempted admin command: /{parsed.command}"
            )
            return self._format_response("Permesso negato")

        # Execute command
        try:
            logger.info(
                f"Executing /{parsed.command} from {ctx.sender_display}"
            )
            result = await command.execute(ctx, parsed.args)

            # Record command execution for rate limiting
            if self.rate_limiter and result.success:
                self.rate_limiter.record(sender_key)

            if result.success:
                logger.debug(f"Command successful: {result.response[:50]}...")
            else:
                logger.debug(f"Command failed: {result.error or result.response}")

            return result.response

        except Exception as e:
            logger.exception(f"Error executing /{parsed.command}: {e}")
            return self._format_response("Errore interno")

    def _format_response(self, message: str) -> str:
        """Format a response with the BBS prefix."""
        return f"{self.response_prefix} {message}"

    def get_help_text(self) -> str:
        """Get help text listing all commands."""
        commands = CommandRegistry.get_public_commands()
        cmd_names = sorted([f"/{cmd.name}" for cmd in commands])
        return f"{self.response_prefix} Comandi: {' '.join(cmd_names)}"
