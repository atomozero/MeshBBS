"""
Web server configuration for MeshCore BBS.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

import os
import secrets
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class WebConfig:
    """Configuration for the web interface."""

    # Server settings
    host: str = "0.0.0.0"
    port: int = 8080
    debug: bool = False

    # Security
    secret_key: str = field(default_factory=lambda: os.environ.get(
        "BBS_WEB_SECRET_KEY", secrets.token_urlsafe(32)
    ))
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7

    # Rate limiting for auth
    auth_max_attempts: int = 5
    auth_lockout_minutes: int = 15

    # API Rate limiting
    rate_limit_enabled: bool = True
    rate_limit_auth: int = 200  # Requests per minute for authenticated
    rate_limit_anon: int = 20  # Requests per minute for anonymous
    rate_limit_window: int = 60  # Window in seconds

    # CORS settings
    cors_origins: list = field(default_factory=lambda: ["*"])
    cors_allow_credentials: bool = True

    # Static files
    static_dir: str = "static"

    # API settings
    api_prefix: str = "/api/v1"
    docs_enabled: bool = True

    @classmethod
    def from_env(cls) -> "WebConfig":
        """Create configuration from environment variables."""
        return cls(
            host=os.environ.get("BBS_WEB_HOST", "0.0.0.0"),
            port=int(os.environ.get("BBS_WEB_PORT", "8080")),
            debug=os.environ.get("BBS_WEB_DEBUG", "false").lower() == "true",
            secret_key=os.environ.get(
                "BBS_WEB_SECRET_KEY", secrets.token_urlsafe(32)
            ),
            jwt_access_token_expire_minutes=int(
                os.environ.get("BBS_WEB_JWT_EXPIRE_MINUTES", "15")
            ),
            jwt_refresh_token_expire_days=int(
                os.environ.get("BBS_WEB_JWT_REFRESH_DAYS", "7")
            ),
            auth_max_attempts=int(
                os.environ.get("BBS_WEB_AUTH_MAX_ATTEMPTS", "5")
            ),
            auth_lockout_minutes=int(
                os.environ.get("BBS_WEB_AUTH_LOCKOUT_MINUTES", "15")
            ),
            docs_enabled=os.environ.get(
                "BBS_WEB_DOCS_ENABLED", "true"
            ).lower() == "true",
            rate_limit_enabled=os.environ.get(
                "BBS_WEB_RATE_LIMIT_ENABLED", "true"
            ).lower() == "true",
            rate_limit_auth=int(
                os.environ.get("BBS_WEB_RATE_LIMIT_AUTH", "200")
            ),
            rate_limit_anon=int(
                os.environ.get("BBS_WEB_RATE_LIMIT_ANON", "20")
            ),
            rate_limit_window=int(
                os.environ.get("BBS_WEB_RATE_LIMIT_WINDOW", "60")
            ),
        )


# Global config instance
_config: Optional[WebConfig] = None


def get_web_config() -> WebConfig:
    """Get the web configuration instance."""
    global _config
    if _config is None:
        _config = WebConfig.from_env()
    return _config


def set_web_config(config: WebConfig) -> None:
    """Set the web configuration instance."""
    global _config
    _config = config


def reset_web_config() -> None:
    """Reset the web configuration (for testing)."""
    global _config
    _config = None
