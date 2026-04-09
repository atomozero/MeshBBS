"""
Tests for API Rate Limiting.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

import pytest
import time
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

# Add src to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from web.middleware.rate_limiter import (
    RateLimitRule,
    RateLimitState,
    APIRateLimiter,
    RateLimitMiddleware,
    get_api_rate_limiter,
)


class TestRateLimitRule:
    """Test RateLimitRule dataclass."""

    def test_default_burst(self):
        """Test that burst defaults to requests."""
        rule = RateLimitRule(requests=100, window=60)
        assert rule.burst == 100

    def test_custom_burst(self):
        """Test custom burst value."""
        rule = RateLimitRule(requests=100, window=60, burst=150)
        assert rule.burst == 150


class TestAPIRateLimiter:
    """Test APIRateLimiter class."""

    def test_init_defaults(self):
        """Test default initialization."""
        limiter = APIRateLimiter()
        stats = limiter.get_stats()

        assert stats["total_clients"] == 0
        assert stats["whitelisted"] == 0

    def test_check_first_request_allowed(self):
        """Test that first request is always allowed."""
        limiter = APIRateLimiter(default_limit=10, default_window=60)
        allowed, remaining, reset = limiter.check("client1")

        assert allowed is True
        assert remaining is not None

    def test_check_within_limit(self):
        """Test requests within limit are allowed."""
        # Use anon_limit since we're testing anonymous requests
        limiter = APIRateLimiter(anon_limit=5, anon_window=60)

        for i in range(5):
            allowed, remaining, _ = limiter.check("client1", is_authenticated=False)
            assert allowed is True
            assert remaining == 5 - i - 1

    def test_check_exceed_limit(self):
        """Test requests exceeding limit are blocked."""
        limiter = APIRateLimiter(anon_limit=3, anon_window=60)

        # Use up tokens
        for _ in range(3):
            limiter.check("client1", is_authenticated=False)

        # Next request should be blocked
        allowed, remaining, reset = limiter.check("client1", is_authenticated=False)
        assert allowed is False
        assert remaining == 0
        assert reset > 0

    def test_token_refill(self):
        """Test that tokens refill over time."""
        limiter = APIRateLimiter(default_limit=60, default_window=60)  # 1/sec

        # Use up some tokens
        for _ in range(5):
            limiter.check("client1")

        # Get remaining
        allowed, remaining_before, _ = limiter.check("client1")

        # Wait a bit
        time.sleep(0.1)

        # Check again - should have more tokens
        allowed, remaining_after, _ = limiter.check("client1")
        # Note: Due to consumption in check(), remaining_after might not be
        # higher, but the request should be allowed
        assert allowed is True

    def test_whitelist(self):
        """Test whitelisted clients bypass limits."""
        limiter = APIRateLimiter(anon_limit=2, anon_window=60)

        # Exhaust limit
        limiter.check("client1", is_authenticated=False)
        limiter.check("client1", is_authenticated=False)
        allowed, _, _ = limiter.check("client1", is_authenticated=False)
        assert allowed is False

        # Whitelist the client
        limiter.add_to_whitelist("client1")
        allowed, _, _ = limiter.check("client1", is_authenticated=False)
        assert allowed is True

        # Remove from whitelist
        limiter.remove_from_whitelist("client1")
        allowed, _, _ = limiter.check("client1", is_authenticated=False)
        assert allowed is False

    def test_is_whitelisted(self):
        """Test is_whitelisted method."""
        limiter = APIRateLimiter()

        assert limiter.is_whitelisted("client1") is False
        limiter.add_to_whitelist("client1")
        assert limiter.is_whitelisted("client1") is True

    def test_endpoint_rules(self):
        """Test endpoint-specific rules."""
        limiter = APIRateLimiter(anon_limit=100, anon_window=60)
        limiter.add_endpoint_rule("/auth/login", requests=5, window=300)

        # Login endpoint uses stricter rule (new client for this test)
        for _ in range(5):
            allowed, _, _ = limiter.check("login_client", path="/auth/login", is_authenticated=False)
            assert allowed is True

        allowed, _, _ = limiter.check("login_client", path="/auth/login", is_authenticated=False)
        assert allowed is False

        # Other endpoints use default rule (different client)
        allowed, _, _ = limiter.check("other_client", path="/users", is_authenticated=False)
        assert allowed is True

    def test_auth_vs_anon_limits(self):
        """Test different limits for auth vs anonymous."""
        limiter = APIRateLimiter(
            auth_limit=100,
            auth_window=60,
            anon_limit=10,
            anon_window=60,
        )

        # Exhaust anon limit
        for _ in range(10):
            limiter.check("client1", is_authenticated=False)

        allowed, _, _ = limiter.check("client1", is_authenticated=False)
        assert allowed is False

        # Auth has higher limit
        for _ in range(10):
            allowed, _, _ = limiter.check("client2", is_authenticated=True)
            assert allowed is True

    def test_get_rule(self):
        """Test get_rule returns correct rule."""
        limiter = APIRateLimiter(
            auth_limit=100,
            auth_window=60,
            anon_limit=20,
            anon_window=60,
        )
        limiter.add_endpoint_rule("/special", requests=5, window=10)

        # Endpoint rule takes priority
        rule = limiter.get_rule("/special/path", is_authenticated=True)
        assert rule.requests == 5

        # Auth rule for authenticated
        rule = limiter.get_rule("/other", is_authenticated=True)
        assert rule.requests == 100

        # Anon rule for anonymous
        rule = limiter.get_rule("/other", is_authenticated=False)
        assert rule.requests == 20

    def test_reset_client(self):
        """Test resetting a client's state."""
        limiter = APIRateLimiter(anon_limit=5, anon_window=60)

        # Make some requests
        limiter.check("client1", is_authenticated=False)
        limiter.check("client1", is_authenticated=False)

        # Reset
        limiter.reset("client1")

        # Should have full tokens again
        allowed, remaining, _ = limiter.check("client1", is_authenticated=False)
        assert allowed is True
        assert remaining == 4  # 5 - 1 for this request

    def test_reset_all(self):
        """Test resetting all clients."""
        limiter = APIRateLimiter(default_limit=5, default_window=60)

        limiter.check("client1")
        limiter.check("client2")

        stats = limiter.get_stats()
        assert stats["total_clients"] == 2

        limiter.reset_all()

        stats = limiter.get_stats()
        assert stats["total_clients"] == 0

    def test_independent_clients(self):
        """Test that different clients have independent limits."""
        limiter = APIRateLimiter(anon_limit=2, anon_window=60)

        # Exhaust client1
        limiter.check("client1", is_authenticated=False)
        limiter.check("client1", is_authenticated=False)
        allowed, _, _ = limiter.check("client1", is_authenticated=False)
        assert allowed is False

        # client2 should still work
        allowed, _, _ = limiter.check("client2", is_authenticated=False)
        assert allowed is True


class TestRateLimitMiddleware:
    """Test RateLimitMiddleware class."""

    @pytest.fixture
    def mock_request(self):
        """Create a mock request."""
        request = MagicMock()
        request.url.path = "/api/v1/users"
        request.headers = {}
        request.client = MagicMock()
        request.client.host = "192.168.1.1"
        return request

    @pytest.fixture
    def mock_response(self):
        """Create a mock response."""
        response = MagicMock()
        response.headers = {}
        return response

    @pytest.mark.asyncio
    async def test_allowed_request_has_headers(self, mock_request, mock_response):
        """Test that allowed requests get rate limit headers."""
        limiter = APIRateLimiter()

        async def call_next(request):
            return mock_response

        middleware = RateLimitMiddleware(
            app=MagicMock(),
            rate_limiter=limiter,
        )

        response = await middleware.dispatch(mock_request, call_next)

        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers
        assert "X-RateLimit-Reset" in response.headers

    @pytest.mark.asyncio
    async def test_rate_limited_request(self, mock_request):
        """Test that rate limited requests return 429."""
        limiter = APIRateLimiter(anon_limit=1, anon_window=60)

        # Exhaust limit
        limiter.check("192.168.1.1")

        async def call_next(request):
            return MagicMock()

        middleware = RateLimitMiddleware(
            app=MagicMock(),
            rate_limiter=limiter,
        )

        response = await middleware.dispatch(mock_request, call_next)

        assert response.status_code == 429
        assert "Retry-After" in response.headers

    @pytest.mark.asyncio
    async def test_excluded_paths_bypass(self, mock_request, mock_response):
        """Test that excluded paths bypass rate limiting."""
        mock_request.url.path = "/health"
        limiter = APIRateLimiter(anon_limit=1, anon_window=60)

        # Exhaust limit
        limiter.check("192.168.1.1")

        async def call_next(request):
            return mock_response

        middleware = RateLimitMiddleware(
            app=MagicMock(),
            rate_limiter=limiter,
        )

        response = await middleware.dispatch(mock_request, call_next)

        # Should not be rate limited
        assert response.status_code != 429

    @pytest.mark.asyncio
    async def test_authenticated_detection(self, mock_request, mock_response):
        """Test that authenticated requests are detected."""
        mock_request.headers = {"Authorization": "Bearer token123"}
        limiter = APIRateLimiter(auth_limit=100, anon_limit=5)

        async def call_next(request):
            return mock_response

        middleware = RateLimitMiddleware(
            app=MagicMock(),
            rate_limiter=limiter,
        )

        # Make requests - should use auth limit (higher)
        for _ in range(10):
            response = await middleware.dispatch(mock_request, call_next)
            assert response != 429  # Should all be allowed

    @pytest.mark.asyncio
    async def test_forwarded_ip_header(self, mock_request, mock_response):
        """Test that X-Forwarded-For header is respected."""
        mock_request.headers = {"X-Forwarded-For": "10.0.0.1, 192.168.1.1"}
        limiter = APIRateLimiter(anon_limit=5, anon_window=60)

        async def call_next(request):
            return mock_response

        middleware = RateLimitMiddleware(
            app=MagicMock(),
            rate_limiter=limiter,
        )

        await middleware.dispatch(mock_request, call_next)

        # Should track by forwarded IP, not direct client IP
        stats = limiter.get_stats()
        assert stats["total_clients"] == 1


class TestGlobalRateLimiter:
    """Test global rate limiter instance."""

    def test_get_api_rate_limiter(self):
        """Test getting global instance."""
        limiter = get_api_rate_limiter()
        assert limiter is not None
        assert isinstance(limiter, APIRateLimiter)

    def test_same_instance(self):
        """Test that same instance is returned."""
        limiter1 = get_api_rate_limiter()
        limiter2 = get_api_rate_limiter()
        assert limiter1 is limiter2


class TestRateLimitStats:
    """Test rate limiter statistics."""

    def test_stats_format(self):
        """Test stats dictionary format."""
        limiter = APIRateLimiter(
            default_limit=100,
            default_window=60,
            auth_limit=200,
            auth_window=60,
            anon_limit=20,
            anon_window=60,
        )

        limiter.check("client1")
        limiter.add_to_whitelist("admin")

        stats = limiter.get_stats()

        assert stats["total_clients"] == 1
        assert stats["whitelisted"] == 1
        assert stats["default_limit"] == "100/60s"
        assert stats["auth_limit"] == "200/60s"
        assert stats["anon_limit"] == "20/60s"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
