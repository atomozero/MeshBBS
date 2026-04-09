"""
Tests for lightweight bottle web server.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

import pytest
import json
import sys
import io
from unittest.mock import patch, MagicMock

from web_light.server import app, _sessions, _admin_username, _admin_password, _format_uptime


def wsgi_request(path, method="GET", cookie=None):
    """Make a WSGI request to the bottle app and return (status, headers, body)."""
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "SERVER_NAME": "localhost",
        "SERVER_PORT": "8080",
        "SERVER_PROTOCOL": "HTTP/1.1",
        "HTTP_HOST": "localhost:8080",
        "wsgi.input": io.BytesIO(),
        "wsgi.errors": io.StringIO(),
        "wsgi.url_scheme": "http",
    }
    if cookie:
        environ["HTTP_COOKIE"] = cookie

    status_line = [None]
    response_headers = [None]

    def start_response(status, headers, exc_info=None):
        status_line[0] = status
        response_headers[0] = headers

    body = app.wsgi(environ, start_response)
    html = b"".join(body).decode("utf-8", errors="replace")

    return status_line[0], response_headers[0], html


class TestAuth:
    """Tests for authentication."""

    def test_login_page_renders(self):
        """GET /login returns login form."""
        status, headers, body = wsgi_request("/login")
        assert "200" in status
        assert "MeshBBS" in body
        assert "password" in body

    def test_dashboard_requires_auth(self):
        """GET / without auth redirects to /login."""
        status, headers, body = wsgi_request("/")
        assert "303" in status

    def test_users_requires_auth(self):
        """GET /users without auth redirects."""
        status, headers, body = wsgi_request("/users")
        assert "303" in status

    def test_messages_requires_auth(self):
        """GET /messages without auth redirects."""
        status, headers, body = wsgi_request("/messages")
        assert "303" in status

    def test_health_no_auth(self):
        """GET /api/health works without auth."""
        status, headers, body = wsgi_request("/api/health")
        assert "200" in status
        data = json.loads(body)
        assert "status" in data
        assert "radio_connected" in data


class TestHelpers:
    """Tests for helper functions."""

    def test_format_uptime_minutes(self):
        assert _format_uptime(300) == "5m"

    def test_format_uptime_hours(self):
        assert _format_uptime(7200) == "2h 0m"

    def test_format_uptime_days(self):
        assert _format_uptime(90000) == "1g 1h 0m"

    def test_format_uptime_zero(self):
        assert _format_uptime(0) == "N/A"

    def test_format_uptime_none(self):
        assert _format_uptime(None) == "N/A"


class TestSessionStore:
    """Tests for session management."""

    def test_sessions_dict_exists(self):
        assert isinstance(_sessions, dict)

    def test_default_credentials(self):
        assert _admin_username is not None
        assert _admin_password is not None
