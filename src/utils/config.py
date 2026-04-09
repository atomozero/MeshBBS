"""
Configuration management for MeshCore BBS.

Supports:
- Environment variables (highest priority)
- JSON config file (persistent settings)
- Defaults (fallback)

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

import os
import json
import logging
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)

# Fields that can be updated via API (not hardware/path settings)
UPDATABLE_FIELDS = {
    "bbs_name",
    "default_area",
    "max_message_length",
    "messages_per_page",
    "pm_retention_days",
    "activity_log_retention_days",
    "allow_ephemeral_pm",
    "min_message_interval",
    "max_messages_per_minute",
    "advert_interval_minutes",
    "response_prefix",
    "latitude",
    "longitude",
    "send_delay",
    "max_send_attempts",
    "send_retry_delay",
    "stats_publish_interval",
    "beacon_interval",
    "beacon_message",
}


@dataclass
class Config:
    """Application configuration with sensible defaults."""

    # Connection mode: "serial" or "tcp"
    connection_mode: str = "serial"

    # Serial connection
    serial_port: str = "/dev/ttyUSB0"
    baud_rate: int = 115200
    serial_timeout: float = 1.0

    # TCP connection
    tcp_host: str = "192.168.1.100"
    tcp_port: int = 5000

    # Database
    database_path: str = "data/bbs.db"
    database_key: Optional[str] = None  # SQLCipher encryption key (None = no encryption)

    # Logging
    log_path: str = "logs/bbs.log"
    log_level: str = "INFO"

    # BBS Settings
    bbs_name: str = "MeshCore BBS"
    default_area: str = "generale"
    max_message_length: int = 200
    messages_per_page: int = 5

    # Rate limiting
    min_message_interval: float = 1.0  # seconds between messages
    max_messages_per_minute: int = 30

    # Send throttling (delay between chunked responses over radio)
    send_delay: float = 3.0  # seconds between chunks when sending multi-line responses
    max_send_attempts: int = 2  # max retry attempts for send_msg_with_retry
    send_retry_delay: float = 2.0  # seconds between retry attempts

    # Advert settings
    advert_interval_minutes: int = 180  # 3 hours like repeaters

    # Beacon broadcast (0 = disabled)
    beacon_interval: int = 0  # minutes between beacon broadcasts (0=off)
    beacon_message: str = "{name} attivo! Scrivi !help per i comandi"

    # Statistics publishing interval (MQTT)
    stats_publish_interval: int = 300  # seconds (5 minutes)

    # Response prefix
    response_prefix: str = "[BBS]"

    # Location (optional BBS coordinates for adverts)
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    # Privacy settings (GDPR compliance)
    pm_retention_days: int = 30  # Days to keep PMs (0 = forever)
    activity_log_retention_days: int = 90  # Days to keep activity logs (0 = forever)
    allow_ephemeral_pm: bool = True  # Allow users to send non-saved PMs

    # Paths (computed)
    # base_path: config.py -> utils/ -> src/ -> project root
    base_path: Path = field(default_factory=lambda: Path(__file__).parent.parent.parent)

    # Config file path
    config_file_path: str = field(default="")

    @property
    def has_location(self) -> bool:
        """Check if BBS location coordinates are configured."""
        return self.latitude is not None and self.longitude is not None

    def __post_init__(self):
        """Resolve relative paths."""
        if not os.path.isabs(self.database_path):
            self.database_path = str(self.base_path / self.database_path)
        if not os.path.isabs(self.log_path):
            self.log_path = str(self.base_path / self.log_path)
        if not self.config_file_path:
            self.config_file_path = str(self.base_path / "data" / "settings.json")

    @classmethod
    def from_env(cls) -> "Config":
        """Create configuration from environment variables."""
        config = cls(
            serial_port=os.getenv("BBS_SERIAL_PORT", "/dev/ttyUSB0"),
            baud_rate=int(os.getenv("BBS_BAUD_RATE", "115200")),
            database_path=os.getenv("BBS_DATABASE_PATH", "data/bbs.db"),
            database_key=os.getenv("BBS_DATABASE_KEY", None),
            log_path=os.getenv("BBS_LOG_PATH", "logs/bbs.log"),
            log_level=os.getenv("BBS_LOG_LEVEL", "INFO"),
            bbs_name=os.getenv("BBS_NAME", "MeshCore BBS"),
            default_area=os.getenv("BBS_DEFAULT_AREA", "generale"),
            pm_retention_days=int(os.getenv("BBS_PM_RETENTION_DAYS", "30")),
            activity_log_retention_days=int(os.getenv("BBS_LOG_RETENTION_DAYS", "90")),
            allow_ephemeral_pm=os.getenv("BBS_ALLOW_EPHEMERAL_PM", "true").lower() == "true",
            latitude=float(os.environ["BBS_LATITUDE"]) if "BBS_LATITUDE" in os.environ else None,
            longitude=float(os.environ["BBS_LONGITUDE"]) if "BBS_LONGITUDE" in os.environ else None,
        )

        # Load persistent settings from file (overrides defaults, but env vars have priority)
        config._load_from_file()

        return config

    def _load_from_file(self) -> None:
        """Load settings from JSON config file."""
        try:
            if os.path.exists(self.config_file_path):
                with open(self.config_file_path, "r", encoding="utf-8") as f:
                    saved = json.load(f)

                # Only update fields that aren't set via environment variables
                for key, value in saved.items():
                    if key in UPDATABLE_FIELDS and hasattr(self, key):
                        env_key = f"BBS_{key.upper()}"
                        # Don't override if env var is set
                        if env_key not in os.environ:
                            setattr(self, key, value)

                logger.debug(f"Loaded settings from {self.config_file_path}")
        except Exception as e:
            logger.warning(f"Could not load settings file: {e}")

    def save_to_file(self) -> bool:
        """Save updatable settings to JSON config file."""
        try:
            # Ensure directory exists
            Path(self.config_file_path).parent.mkdir(parents=True, exist_ok=True)

            # Only save updatable fields
            data = {k: getattr(self, k) for k in UPDATABLE_FIELDS if hasattr(self, k)}

            with open(self.config_file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            logger.info(f"Saved settings to {self.config_file_path}")
            return True
        except Exception as e:
            logger.error(f"Could not save settings file: {e}")
            return False

    def update(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update configuration with new values.

        Args:
            updates: Dictionary of field names and new values

        Returns:
            Dictionary of actually updated fields
        """
        updated = {}

        for key, value in updates.items():
            if key not in UPDATABLE_FIELDS:
                logger.warning(f"Attempted to update non-updatable field: {key}")
                continue

            if not hasattr(self, key):
                logger.warning(f"Unknown config field: {key}")
                continue

            old_value = getattr(self, key)
            if old_value != value:
                setattr(self, key, value)
                updated[key] = {"old": old_value, "new": value}
                logger.info(f"Config updated: {key} = {value}")

        # Persist changes
        if updated:
            self.save_to_file()

        return updated

    def to_dict(self, include_sensitive: bool = False) -> Dict[str, Any]:
        """
        Convert config to dictionary.

        Args:
            include_sensitive: Include sensitive fields like database_key
        """
        data = {}
        for key in UPDATABLE_FIELDS:
            if hasattr(self, key):
                data[key] = getattr(self, key)

        # Add read-only fields
        data["serial_port"] = self.serial_port
        data["baud_rate"] = self.baud_rate
        data["database_path"] = self.database_path
        data["log_path"] = self.log_path

        if include_sensitive and self.database_key:
            data["database_key"] = "***"  # Never expose actual key

        return data

    def ensure_directories(self):
        """Create necessary directories if they don't exist."""
        Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        Path(self.log_path).parent.mkdir(parents=True, exist_ok=True)
        Path(self.config_file_path).parent.mkdir(parents=True, exist_ok=True)


# Global configuration instance
_config: Optional[Config] = None


def get_config() -> Config:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = Config.from_env()
        _config.ensure_directories()
    return _config


def set_config(config: Config):
    """Set the global configuration instance."""
    global _config
    _config = config


def reload_config() -> Config:
    """Reload configuration from environment and file."""
    global _config
    _config = Config.from_env()
    _config.ensure_directories()
    return _config
