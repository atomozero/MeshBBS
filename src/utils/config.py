"""
Configuration management for MeshCore BBS.

Precedence (highest first):
1. command line arguments (launcher.py)
2. canonical environment variables (BBS_*, see ENV_VARS)
3. legacy unprefixed variables written by older installs (DATABASE_PATH,
   LOG_FILE, LOG_LEVEL, SERIAL_PORT, BAUD_RATE)
4. settings.json (runtime settings saved from the web panel), stored next
   to the database
5. defaults

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

import os
import json
import logging
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any, Tuple
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
    "repeater_monitor_enabled",
    "repeater_monitor_interval_minutes",
    "repeater_monitor_targets",
}


# Environment variables read by Config.from_env():
# field -> (canonical name, legacy names accepted from older installs...)
ENV_VARS: Dict[str, Tuple[str, ...]] = {
    "serial_port": ("BBS_SERIAL_PORT", "SERIAL_PORT"),
    "baud_rate": ("BBS_BAUD_RATE", "BAUD_RATE"),
    "database_path": ("BBS_DATABASE_PATH", "DATABASE_PATH"),
    "database_key": ("BBS_DATABASE_KEY",),
    "log_path": ("BBS_LOG_PATH", "LOG_FILE"),
    "log_level": ("BBS_LOG_LEVEL", "LOG_LEVEL"),
    "bbs_name": ("BBS_NAME",),
    "default_area": ("BBS_DEFAULT_AREA",),
    "pm_retention_days": ("BBS_PM_RETENTION_DAYS",),
    "activity_log_retention_days": ("BBS_LOG_RETENTION_DAYS",),
    "allow_ephemeral_pm": ("BBS_ALLOW_EPHEMERAL_PM",),
    "latitude": ("BBS_LATITUDE",),
    "longitude": ("BBS_LONGITUDE",),
}

_TRUE_VALUES = {"1", "true", "yes", "on"}


def _parse_bool(value: str) -> bool:
    return value.strip().lower() in _TRUE_VALUES


_ENV_CONVERTERS = {
    "baud_rate": int,
    "pm_retention_days": int,
    "activity_log_retention_days": int,
    "allow_ephemeral_pm": _parse_bool,
    "latitude": float,
    "longitude": float,
}


def env_lookup(field_name: str) -> Optional[Tuple[str, str]]:
    """
    Find the environment variable that sets a Config field.

    Returns:
        (variable name, raw value) of the first non-empty variable among the
        canonical and legacy names, or None
    """
    for name in ENV_VARS.get(field_name, ()):
        value = os.environ.get(name)
        if value is not None and value.strip() != "":
            return name, value.strip()
    return None


def read_env_settings() -> Dict[str, Any]:
    """Config fields set through environment variables (converted)."""
    values: Dict[str, Any] = {}
    for field_name in ENV_VARS:
        found = env_lookup(field_name)
        if found is None:
            continue
        name, raw = found
        try:
            values[field_name] = _ENV_CONVERTERS.get(field_name, str)(raw)
        except ValueError:
            logger.warning(f"Ignoring invalid value for {name}: {raw!r}")
            continue
        if name != ENV_VARS[field_name][0]:
            logger.info(f"Legacy variable {name} used: rename it to {ENV_VARS[field_name][0]}")
    return values


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
    # 10s lets the previous chunk propagate through repeaters before the next
    # one enters the mesh, cutting drop rate for multi-hop users.
    send_delay: float = 10.0  # seconds between chunks when sending multi-line responses
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

    # Repeater telemetry monitor
    # List of dicts: [{"name": str, "public_key": str, "password_env": str}, ...]
    repeater_monitor_enabled: bool = False
    repeater_monitor_interval_minutes: int = 30
    repeater_monitor_targets: list = field(default_factory=list)
    repeater_monitor_jsonl_path: str = "data/repeater_telemetry.jsonl"

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
        if self.repeater_monitor_jsonl_path and not os.path.isabs(self.repeater_monitor_jsonl_path):
            self.repeater_monitor_jsonl_path = str(self.base_path / self.repeater_monitor_jsonl_path)
        if not self.config_file_path:
            self.config_file_path = str(self.base_path / "data" / "settings.json")

    @classmethod
    def from_env(cls, overrides: Optional[Dict[str, Any]] = None) -> "Config":
        """
        Create configuration from command line overrides, environment
        variables, settings.json and defaults (in this order of precedence).

        Args:
            overrides: Field values given explicitly (e.g. CLI arguments);
                None values are ignored
        """
        explicit = {k: v for k, v in (overrides or {}).items() if v is not None}
        values = read_env_settings()
        values.update(explicit)
        config = cls(**values)

        # settings.json lives next to the database unless given explicitly
        if "config_file_path" not in explicit:
            config.config_file_path = str(Path(config.database_path).parent / "settings.json")

        # Persistent settings: below CLI and environment, above defaults
        config._load_from_file(skip=set(values))

        return config

    def _load_from_file(self, skip: Optional[set] = None) -> None:
        """
        Load settings from the JSON config file.

        Args:
            skip: Fields not to override (set by CLI or environment). By
                default, the fields set through an environment variable.
        """
        if skip is None:
            skip = {f for f in ENV_VARS if env_lookup(f) is not None}
        try:
            if os.path.exists(self.config_file_path):
                with open(self.config_file_path, "r", encoding="utf-8") as f:
                    saved = json.load(f)

                for key, value in saved.items():
                    if key in UPDATABLE_FIELDS and hasattr(self, key) and key not in skip:
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
