"""
Logging configuration for MeshCore BBS.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

# Log format
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Global logger cache
_loggers: dict = {}


def setup_logger(
    name: str = "meshbbs",
    log_file: Optional[str] = None,
    level: str = "INFO",
    max_bytes: int = 5 * 1024 * 1024,  # 5MB
    backup_count: int = 3,
) -> logging.Logger:
    """
    Setup and configure a logger.

    Args:
        name: Logger name
        log_file: Path to log file (None for console only)
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        max_bytes: Maximum size of log file before rotation
        backup_count: Number of backup files to keep

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)

    # Avoid duplicate handlers
    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    formatter = logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler (if log_file specified)
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    _loggers[name] = logger
    return logger


def get_logger(name: str = "meshbbs") -> logging.Logger:
    """
    Get a logger instance.

    Args:
        name: Logger name (use dot notation for hierarchy, e.g., "meshbbs.commands")

    Returns:
        Logger instance
    """
    if name in _loggers:
        return _loggers[name]

    # Create child logger from root meshbbs logger
    if name.startswith("meshbbs."):
        parent = get_logger("meshbbs")
        logger = logging.getLogger(name)
        _loggers[name] = logger
        return logger

    # Create new logger with default settings
    return setup_logger(name)
