"""
Command dispatcher for MeshCore BBS.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

import importlib
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


# Commands whose arguments contain private text (PM/mail bodies). Only the
# command name and the first argument (target nickname or message id) are
# written to the activity log, never the body.
PRIVATE_COMMANDS = frozenset({
    "msg", "msg!", "mail", "readmail", "delmail", "readpm", "delpm", "reply",
})
# Commands that deliver ephemeral (non-saved) PMs
EPHEMERAL_COMMANDS = frozenset({"msg!"})


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
        # Import here to avoid circular imports. Importing the package runs
        # every command module, whose @CommandRegistry.register decorators
        # register the built-in commands on first import.
        importlib.import_module(__package__)

        # Modules are imported only once: if the registry was cleared after
        # import (tests, plugin reloads), re-register the built-ins.
        CommandRegistry.ensure_builtins()

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

        welcome_msg = ""
        if is_new:
            logger.info(f"New user: {sender_key[:8]}...")
            from utils.config import get_config
            cfg = get_config()
            welcome_msg = (
                f"{self.response_prefix} Benvenuto su {cfg.bbs_name}! "
                f"Usa !help per la lista comandi. "
                f"Imposta il tuo nick con !nick <nome>\n"
            )

        # Check if user is banned or kicked
        if not user.is_active():
            if user.is_banned:
                logger.warning(f"Banned user attempted command: {sender_key[:8]}")
            else:
                logger.warning(f"Kicked user attempted command: {sender_key[:8]}")
            return self._format_response("Accesso negato")

        # Check rate limiting. Admin status is checked on every call (no
        # sticky whitelist: a demoted admin must be limited again).
        rate_limited = self.rate_limiter is not None and not user.is_admin
        if rate_limited:
            allowed, error_msg = self.rate_limiter.check(sender_key)
            if not allowed:
                logger.warning(f"Rate limited: {sender_key[:8]} - {error_msg}")
                return self._format_response(error_msg)
            # Record every attempt (failing, unknown or denied commands too),
            # otherwise a flood of invalid commands is never throttled.
            self.rate_limiter.record(sender_key)

        # Create context
        ctx = CommandContext(
            sender_key=sender_key,
            sender_name=user.nickname,
            raw_message=message,
            timestamp=datetime.utcnow(),
            hops=hops,
            rssi=rssi,
            is_admin=user.is_admin,
            is_moderator=user.is_moderator,
        )

        # Get command handler
        command_class = CommandRegistry.get(parsed.command)

        if not command_class:
            logger.debug(f"Unknown command: !{parsed.command}")
            return self._format_response(
                f"Comando '!{parsed.command}' sconosciuto. Usa !help"
            )

        # Check admin/moderator permission
        command = command_class(self.session)
        if command.admin_only and not self._has_permission(command, user):
            logger.warning(
                f"Non-admin {sender_key[:8]} attempted admin command: !{parsed.command}"
            )
            return self._format_response("Permesso negato")

        # Ephemeral PMs can be disabled by config (allow_ephemeral_pm)
        if command.name in EPHEMERAL_COMMANDS and not self._ephemeral_allowed():
            return self._format_response("PM effimeri disabilitati su questo BBS")

        # Execute command
        try:
            logger.info(
                f"Executing !{parsed.command} from {ctx.sender_display}"
            )
            result = await command.execute(ctx, parsed.args)

            if result.success:
                logger.debug(f"Command successful: {result.response[:50]}...")
            else:
                logger.debug(f"Command failed: {result.error or result.response}")

            try:
                from bbs.models.activity_log import EventType, log_activity
                details = self._log_details(command.name, parsed.command, parsed.args)
                if not result.success:
                    details += " [fail]"
                log_activity(
                    self.session,
                    EventType.COMMAND_EXECUTED,
                    user_key=sender_key,
                    details=details,
                )
            except Exception:
                pass

            resp = result.response
            if welcome_msg:
                resp = welcome_msg + resp
            return resp

        except Exception as e:
            logger.exception(f"Error executing !{parsed.command}: {e}")
            try:
                self.session.rollback()
            except Exception:
                logger.exception("Rollback failed")
            return self._format_response("Errore interno")

    @staticmethod
    def _has_permission(command, user) -> bool:
        """Admin-only commands: admins always, moderators if allowed."""
        if user.is_admin:
            return True
        return bool(getattr(command, "moderator_allowed", False) and user.is_moderator)

    @staticmethod
    def _ephemeral_allowed() -> bool:
        try:
            from utils.config import get_config
            return bool(getattr(get_config(), "allow_ephemeral_pm", True))
        except Exception:
            return True

    @staticmethod
    def _log_details(canonical: str, invoked: str, args) -> str:
        """
        Build the activity-log line for a command.

        Arguments of private commands (PM/mail bodies) are never logged;
        for those only the command name and the target are recorded.
        """
        details = f"!{invoked}"
        if canonical in PRIVATE_COMMANDS:
            if args:
                details += f" {args[0][:32]}"
            return details
        args_str = " ".join(args) if args else ""
        if args_str:
            details += f" {args_str[:80]}"
        return details

    def _format_response(self, message: str) -> str:
        """Format a response with the BBS prefix."""
        return f"{self.response_prefix} {message}"

    def get_help_text(self) -> str:
        """Get help text listing all commands."""
        commands = CommandRegistry.get_public_commands()
        cmd_names = sorted([f"!{cmd.name}" for cmd in commands])
        return f"{self.response_prefix} Comandi: {' '.join(cmd_names)}"
