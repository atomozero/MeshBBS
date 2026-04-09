"""
Tests for BBS control API endpoints.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from web.main import create_app
from web.config import WebConfig, set_web_config, reset_web_config
from web.auth.models import AdminUser, AdminUserRepository
from web.auth.password import hash_password
from web.auth.jwt import create_access_token
from web.dependencies import get_db


@pytest.fixture
def web_config(config) -> WebConfig:
    reset_web_config()
    cfg = WebConfig(debug=True, secret_key="test-secret-key-for-testing-only-32chars")
    set_web_config(cfg)
    yield cfg
    reset_web_config()


@pytest.fixture
def app(web_config, db_session):
    app = create_app(web_config)

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    return app


@pytest.fixture
def client(app) -> TestClient:
    return TestClient(app)


@pytest.fixture
def admin_user(db_session: Session) -> AdminUser:
    repo = AdminUserRepository(db_session)
    admin = repo.create(
        username="bbsadmin",
        password_hash=hash_password("TestPassword123!"),
        is_superadmin=False,
    )
    db_session.commit()
    return admin


@pytest.fixture
def superadmin_user(db_session: Session) -> AdminUser:
    repo = AdminUserRepository(db_session)
    admin = repo.create(
        username="bbssuperadmin",
        password_hash=hash_password("SuperPassword123!"),
        is_superadmin=True,
    )
    db_session.commit()
    return admin


@pytest.fixture
def admin_headers(admin_user, web_config) -> dict:
    token = create_access_token(
        admin_id=admin_user.id,
        username=admin_user.username,
        is_superadmin=admin_user.is_superadmin,
        secret_key=web_config.secret_key,
        expire_minutes=15,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def superadmin_headers(superadmin_user, web_config) -> dict:
    token = create_access_token(
        admin_id=superadmin_user.id,
        username=superadmin_user.username,
        is_superadmin=superadmin_user.is_superadmin,
        secret_key=web_config.secret_key,
        expire_minutes=15,
    )
    return {"Authorization": f"Bearer {token}"}


class TestBBSStatus:
    """Tests for GET /api/v1/bbs/status."""

    def test_status_authenticated(self, client, admin_headers):
        """Authenticated admin can get BBS status."""
        response = client.get("/api/v1/bbs/status", headers=admin_headers)
        assert response.status_code == 200

        data = response.json()
        assert "radio" in data
        assert "timestamp" in data

    def test_status_unauthenticated(self, client):
        """Unauthenticated request is rejected."""
        response = client.get("/api/v1/bbs/status")
        assert response.status_code in (401, 403)

    def test_status_contains_radio_info(self, client, admin_headers):
        """Status response contains radio connection details."""
        response = client.get("/api/v1/bbs/status", headers=admin_headers)
        data = response.json()

        radio = data["radio"]
        assert "status" in radio
        assert "is_connected" in radio
        assert "message_count" in radio


class TestBBSRestart:
    """Tests for POST /api/v1/bbs/restart."""

    def test_restart_requires_superadmin(self, client, admin_headers):
        """Regular admin cannot restart BBS."""
        response = client.post("/api/v1/bbs/restart", headers=admin_headers)
        assert response.status_code == 403

    def test_restart_unauthenticated(self, client):
        """Unauthenticated request is rejected."""
        response = client.post("/api/v1/bbs/restart")
        assert response.status_code in (401, 403)

    def test_restart_no_bbs_instance(self, client, superadmin_headers):
        """Restart returns 503 when BBS is not running."""
        with patch("launcher.get_bbs_instance", return_value=None):
            response = client.post("/api/v1/bbs/restart", headers=superadmin_headers)
        assert response.status_code == 503

    def test_restart_success(self, client, superadmin_headers):
        """Restart returns success when BBS is running."""
        mock_bbs = MagicMock()
        mock_bbs._running = True
        mock_bbs.stop = AsyncMock()

        with patch("launcher.get_bbs_instance", return_value=mock_bbs):
            response = client.post("/api/v1/bbs/restart", headers=superadmin_headers)

        assert response.status_code == 200
        data = response.json()
        assert "Riavvio" in data["message"]


class TestBBSAdvert:
    """Tests for POST /api/v1/bbs/advert."""

    def test_advert_unauthenticated(self, client):
        """Unauthenticated request is rejected."""
        response = client.post("/api/v1/bbs/advert")
        assert response.status_code in (401, 403)

    def test_advert_no_bbs(self, client, admin_headers):
        """Advert returns 503 when BBS is not running."""
        with patch("launcher.get_bbs_instance", return_value=None):
            response = client.post("/api/v1/bbs/advert", headers=admin_headers)
        assert response.status_code == 503

    def test_advert_success(self, client, admin_headers):
        """Advert returns success when sent."""
        mock_bbs = MagicMock()
        mock_bbs._running = True
        mock_bbs.connection = MagicMock()
        mock_bbs.connection.send_advert = AsyncMock(return_value=True)

        with patch("launcher.get_bbs_instance", return_value=mock_bbs):
            response = client.post("/api/v1/bbs/advert", headers=admin_headers)

        assert response.status_code == 200
        assert "Advertisement" in response.json()["message"]
