"""
API Rate Limiting Middleware for MeshCore BBS.

Implements token bucket rate limiting with Redis-like in-memory storage.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

import asyncio
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, Optional, Callable, Awaitable, Set

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse


logger = logging.getLogger(__name__)


@dataclass
class RateLimitRule:
    """Rate limit rule configuration."""

    requests: int  # Max requests
    window: int  # Time window in seconds
    burst: Optional[int] = None  # Burst allowance (defaults to requests)

    def __post_init__(self):
        if self.burst is None:
            self.burst = self.requests


@dataclass
class RateLimitState:
    """Rate limit state for a client."""

    tokens: float
    last_update: float
    requests_made: int = 0

    def __post_init__(self):
        self.requests_made = 0


class APIRateLimiter:
    """
    Token bucket rate limiter for API endpoints.

    Supports:
    - Per-client rate limiting
    - Different limits for authenticated vs anonymous
    - Endpoint-specific limits
    - Whitelist for admins
    """

    def __init__(
        self,
        default_limit: int = 100,
        default_window: int = 60,
        auth_limit: int = 200,
        auth_window: int = 60,
        anon_limit: int = 20,
        anon_window: int = 60,
        cleanup_interval: int = 300,
    ):
        """
        Initialize the rate limiter.

        Args:
            default_limit: Default requests per window
            default_window: Default time window in seconds
            auth_limit: Limit for authenticated users
            auth_window: Window for authenticated users
            anon_limit: Limit for anonymous users
            anon_window: Window for anonymous users
            cleanup_interval: Interval to cleanup stale entries
        """
        self._default_rule = RateLimitRule(default_limit, default_window)
        self._auth_rule = RateLimitRule(auth_limit, auth_window)
        self._anon_rule = RateLimitRule(anon_limit, anon_window)

        # State storage: client_key -> RateLimitState
        self._states: Dict[str, RateLimitState] = {}

        # Endpoint-specific rules: path_pattern -> RateLimitRule
        self._endpoint_rules: Dict[str, RateLimitRule] = {}

        # Whitelisted clients (bypass rate limiting)
        self._whitelist: Set[str] = set()

        # Cleanup
        self._cleanup_interval = cleanup_interval
        self._last_cleanup = time.time()

    def add_endpoint_rule(
        self,
        path_pattern: str,
        requests: int,
        window: int,
    ) -> None:
        """
        Add a rate limit rule for a specific endpoint.

        Args:
            path_pattern: URL path pattern (e.g., "/auth/login")
            requests: Max requests
            window: Time window in seconds
        """
        self._endpoint_rules[path_pattern] = RateLimitRule(requests, window)

    def add_to_whitelist(self, client_key: str) -> None:
        """Add a client to the whitelist."""
        self._whitelist.add(client_key)

    def remove_from_whitelist(self, client_key: str) -> None:
        """Remove a client from the whitelist."""
        self._whitelist.discard(client_key)

    def is_whitelisted(self, client_key: str) -> bool:
        """Check if a client is whitelisted."""
        return client_key in self._whitelist

    def get_rule(
        self,
        path: str,
        is_authenticated: bool,
    ) -> RateLimitRule:
        """
        Get the applicable rate limit rule.

        Args:
            path: Request path
            is_authenticated: Whether the request is authenticated

        Returns:
            Applicable RateLimitRule
        """
        # Check endpoint-specific rules
        for pattern, rule in self._endpoint_rules.items():
            if path.startswith(pattern):
                return rule

        # Use auth/anon rules
        if is_authenticated:
            return self._auth_rule
        return self._anon_rule

    def check(
        self,
        client_key: str,
        path: str = "/",
        is_authenticated: bool = False,
    ) -> tuple[bool, Optional[int], Optional[int]]:
        """
        Check if a request is allowed.

        Args:
            client_key: Client identifier (IP or user ID)
            path: Request path
            is_authenticated: Whether the request is authenticated

        Returns:
            Tuple of (allowed, remaining, reset_after)
        """
        # Bypass for whitelisted clients
        if client_key in self._whitelist:
            return True, None, None

        # Periodic cleanup
        self._maybe_cleanup()

        # Get applicable rule
        rule = self.get_rule(path, is_authenticated)

        # Get or create state
        now = time.time()
        state = self._states.get(client_key)

        if state is None:
            # New client
            state = RateLimitState(
                tokens=float(rule.burst),
                last_update=now,
            )
            self._states[client_key] = state

        # Refill tokens (token bucket algorithm)
        time_passed = now - state.last_update
        refill_rate = rule.requests / rule.window
        tokens_to_add = time_passed * refill_rate
        state.tokens = min(rule.burst, state.tokens + tokens_to_add)
        state.last_update = now

        # Check if request is allowed
        if state.tokens >= 1:
            state.tokens -= 1
            state.requests_made += 1
            remaining = int(state.tokens)
            reset_after = int(rule.window - (now % rule.window))
            return True, remaining, reset_after

        # Rate limited
        remaining = 0
        reset_after = int((1 - state.tokens) / refill_rate)
        return False, remaining, reset_after

    def _maybe_cleanup(self) -> None:
        """Cleanup stale entries periodically."""
        now = time.time()
        if now - self._last_cleanup < self._cleanup_interval:
            return

        self._last_cleanup = now
        cutoff = now - max(
            self._default_rule.window,
            self._auth_rule.window,
            self._anon_rule.window,
        ) * 2

        # Remove old entries
        stale_keys = [
            key for key, state in self._states.items()
            if state.last_update < cutoff
        ]
        for key in stale_keys:
            del self._states[key]

        if stale_keys:
            logger.debug(f"Cleaned up {len(stale_keys)} stale rate limit entries")

    def get_stats(self) -> Dict:
        """Get rate limiter statistics."""
        return {
            "total_clients": len(self._states),
            "whitelisted": len(self._whitelist),
            "endpoint_rules": len(self._endpoint_rules),
            "default_limit": f"{self._default_rule.requests}/{self._default_rule.window}s",
            "auth_limit": f"{self._auth_rule.requests}/{self._auth_rule.window}s",
            "anon_limit": f"{self._anon_rule.requests}/{self._anon_rule.window}s",
        }

    def reset(self, client_key: str) -> None:
        """Reset rate limit state for a client."""
        self._states.pop(client_key, None)

    def reset_all(self) -> None:
        """Reset all rate limit states."""
        self._states.clear()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    FastAPI/Starlette middleware for API rate limiting.

    Adds rate limit headers to responses:
    - X-RateLimit-Limit: Maximum requests per window
    - X-RateLimit-Remaining: Remaining requests
    - X-RateLimit-Reset: Seconds until limit resets
    - Retry-After: Seconds to wait (when rate limited)
    """

    def __init__(
        self,
        app,
        rate_limiter: Optional[APIRateLimiter] = None,
        key_func: Optional[Callable[[Request], str]] = None,
        exclude_paths: Optional[Set[str]] = None,
    ):
        """
        Initialize the middleware.

        Args:
            app: ASGI application
            rate_limiter: Rate limiter instance
            key_func: Function to extract client key from request
            exclude_paths: Paths to exclude from rate limiting
        """
        super().__init__(app)
        self.limiter = rate_limiter or APIRateLimiter()
        self.key_func = key_func or self._default_key_func
        self.exclude_paths = exclude_paths or {
            "/health",
            "/api/v1/radio/health",
            "/docs",
            "/redoc",
            "/openapi.json",
        }

    @staticmethod
    def _default_key_func(request: Request) -> str:
        """Default function to extract client key."""
        # Try to get forwarded IP (behind proxy)
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()

        # Fall back to direct client IP
        if request.client:
            return request.client.host

        return "unknown"

    def _is_authenticated(self, request: Request) -> bool:
        """Check if request is authenticated."""
        auth_header = request.headers.get("Authorization", "")
        return auth_header.startswith("Bearer ")

    def _get_user_id(self, request: Request) -> Optional[str]:
        """Get user ID from request if authenticated."""
        # This would need integration with the JWT verification
        # For now, just return None
        return None

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Process the request and apply rate limiting."""
        path = request.url.path

        # Skip excluded paths
        if any(path.startswith(p) for p in self.exclude_paths):
            return await call_next(request)

        # Get client key
        client_key = self.key_func(request)
        is_authenticated = self._is_authenticated(request)

        # For authenticated users, use user ID if available
        user_id = self._get_user_id(request)
        if user_id:
            client_key = f"user:{user_id}"

        # Check rate limit
        allowed, remaining, reset_after = self.limiter.check(
            client_key,
            path,
            is_authenticated,
        )

        if not allowed:
            logger.warning(
                f"Rate limited: {client_key} on {path}"
            )
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Troppe richieste",
                    "detail": "Rate limit superato. Riprova più tardi.",
                    "retry_after": reset_after,
                },
                headers={
                    "Retry-After": str(reset_after),
                    "X-RateLimit-Limit": str(self.limiter.get_rule(path, is_authenticated).requests),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset_after),
                },
            )

        # Process request
        response = await call_next(request)

        # Add rate limit headers
        rule = self.limiter.get_rule(path, is_authenticated)
        if remaining is not None:
            response.headers["X-RateLimit-Limit"] = str(rule.requests)
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            response.headers["X-RateLimit-Reset"] = str(reset_after)

        return response


# Global rate limiter instance
_api_rate_limiter: Optional[APIRateLimiter] = None


def get_api_rate_limiter() -> APIRateLimiter:
    """Get the global API rate limiter instance."""
    global _api_rate_limiter
    if _api_rate_limiter is None:
        _api_rate_limiter = APIRateLimiter()
    return _api_rate_limiter


def set_api_rate_limiter(limiter: APIRateLimiter) -> None:
    """Set the global API rate limiter instance."""
    global _api_rate_limiter
    _api_rate_limiter = limiter
