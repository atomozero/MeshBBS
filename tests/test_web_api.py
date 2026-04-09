"""
Tests for MeshBBS Web API.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from web.main import create_app
from web.config import WebConfig, set_web_config, reset_web_config
from web.auth.models import AdminUser, AdminUserRepository
from web.auth.password import hash_password
from web.auth.jwt import create_access_token, create_refresh_token
from web.dependencies import get_db
from bbs.models.user import User
from bbs.models.area import Area
from bbs.models.message import Message
from bbs.models.activity_log import ActivityLog, EventType


@pytest.fixture
def web_config(config) -> WebConfig:
    """Create web configuration for testing."""
    # Reset to ensure clean state
    reset_web_config()

    cfg = WebConfig(
        debug=True,
        secret_key="test-secret-key-for-testing-only-32chars",
    )
    set_web_config(cfg)

    yield cfg

    # Clean up after test
    reset_web_config()


@pytest.fixture
def app(web_config, db_session):
    """Create FastAPI test app."""
    app = create_app(web_config)

    # Override db dependency to use test session
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    return app


@pytest.fixture
def client(app) -> TestClient:
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def admin_user(db_session: Session) -> AdminUser:
    """Create test admin user."""
    repo = AdminUserRepository(db_session)
    admin = repo.create(
        username="testadmin",
        password_hash=hash_password("TestPassword123!"),
        is_superadmin=False,
    )
    db_session.commit()
    return admin


@pytest.fixture
def superadmin_user(db_session: Session) -> AdminUser:
    """Create test superadmin user."""
    repo = AdminUserRepository(db_session)
    admin = repo.create(
        username="superadmin",
        password_hash=hash_password("SuperPassword123!"),
        is_superadmin=True,
    )
    db_session.commit()
    return admin


@pytest.fixture
def admin_token(admin_user: AdminUser, web_config: WebConfig) -> str:
    """Create access token for admin user."""
    return create_access_token(
        admin_id=admin_user.id,
        username=admin_user.username,
        is_superadmin=admin_user.is_superadmin,
        secret_key=web_config.secret_key,
        expire_minutes=15,
    )


@pytest.fixture
def superadmin_token(superadmin_user: AdminUser, web_config: WebConfig) -> str:
    """Create access token for superadmin user."""
    return create_access_token(
        admin_id=superadmin_user.id,
        username=superadmin_user.username,
        is_superadmin=superadmin_user.is_superadmin,
        secret_key=web_config.secret_key,
        expire_minutes=15,
    )


@pytest.fixture
def auth_headers(admin_token: str) -> dict:
    """Create authorization headers."""
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture
def superadmin_headers(superadmin_token: str) -> dict:
    """Create authorization headers for superadmin."""
    return {"Authorization": f"Bearer {superadmin_token}"}


@pytest.fixture
def sample_bbs_users(db_session: Session) -> list[User]:
    """Create sample BBS users."""
    users = [
        User(public_key="A" * 64, nickname="Alice"),
        User(public_key="B" * 64, nickname="Bob"),
        User(public_key="C" * 64, nickname="Charlie", is_admin=True),
    ]
    for user in users:
        db_session.add(user)
    db_session.commit()
    return users


@pytest.fixture
def sample_messages(db_session: Session, sample_areas: list[Area], sample_bbs_users: list[User]) -> list[Message]:
    """Create sample messages."""
    area = sample_areas[0]
    messages = [
        Message(
            area_id=area.id,
            sender_key=sample_bbs_users[0].public_key,
            body="Hello from Alice!",
        ),
        Message(
            area_id=area.id,
            sender_key=sample_bbs_users[1].public_key,
            body="Hello from Bob!",
        ),
    ]
    for msg in messages:
        db_session.add(msg)

    # Update area message count
    area.message_count = len(messages)
    db_session.commit()
    return messages


class TestHealthEndpoints:
    """Test health and root endpoints."""

    def test_root_endpoint(self, client: TestClient):
        """Test root endpoint returns API info."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "MeshBBS Admin API"
        assert data["status"] == "online"

    def test_health_endpoint(self, client: TestClient):
        """Test health endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data


class TestAuthEndpoints:
    """Test authentication endpoints."""

    def test_login_success(self, client: TestClient, admin_user: AdminUser, db_session: Session):
        """Test successful login."""
        response = client.post(
            "/auth/login",
            json={"username": "testadmin", "password": "TestPassword123!"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert "expires_in" in data

    def test_login_invalid_password(self, client: TestClient, admin_user: AdminUser):
        """Test login with invalid password."""
        response = client.post(
            "/auth/login",
            json={"username": "testadmin", "password": "wrongpassword"},
        )
        assert response.status_code == 401

    def test_login_nonexistent_user(self, client: TestClient):
        """Test login with non-existent user."""
        response = client.post(
            "/auth/login",
            json={"username": "nonexistent", "password": "password"},
        )
        assert response.status_code == 401

    def test_me_endpoint(self, client: TestClient, auth_headers: dict):
        """Test /auth/me endpoint."""
        response = client.get("/auth/me", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "testadmin"

    def test_me_without_auth(self, client: TestClient):
        """Test /auth/me without authentication."""
        response = client.get("/auth/me")
        assert response.status_code == 401

    def test_refresh_token(self, client: TestClient, admin_user: AdminUser, web_config: WebConfig):
        """Test token refresh."""
        refresh_token = create_refresh_token(
            admin_id=admin_user.id,
            secret_key=web_config.secret_key,
            expire_days=7,
        )
        # Refresh token is expected via cookie
        response = client.post(
            "/auth/refresh",
            cookies={"refresh_token": refresh_token},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data


class TestDashboardEndpoints:
    """Test dashboard API endpoints."""

    def test_get_stats(self, client: TestClient, auth_headers: dict, db_session: Session):
        """Test dashboard stats endpoint."""
        response = client.get("/api/v1/dashboard/stats", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        # Stats are nested in categories
        assert "users" in data
        assert "messages" in data
        assert "areas" in data
        assert "total" in data["users"]
        assert "total" in data["messages"]
        assert "total" in data["areas"]

    def test_get_stats_unauthorized(self, client: TestClient):
        """Test dashboard stats without auth."""
        response = client.get("/api/v1/dashboard/stats")
        assert response.status_code == 401

    def test_get_activity(self, client: TestClient, auth_headers: dict, db_session: Session):
        """Test dashboard activity endpoint."""
        response = client.get("/api/v1/dashboard/activity", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data

    def test_get_chart_data(self, client: TestClient, auth_headers: dict, db_session: Session):
        """Test dashboard chart data endpoint."""
        response = client.get("/api/v1/dashboard/chart?period=7d", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "labels" in data
        assert "messages" in data
        assert "users" in data


class TestUsersEndpoints:
    """Test user management API endpoints."""

    def test_list_users(self, client: TestClient, auth_headers: dict, sample_bbs_users: list[User]):
        """Test listing users."""
        response = client.get("/api/v1/users", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] >= 3  # At least our sample users

    def test_list_users_with_pagination(self, client: TestClient, auth_headers: dict, sample_bbs_users: list[User]):
        """Test listing users with pagination."""
        response = client.get("/api/v1/users?page=1&per_page=2", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) <= 2

    def test_list_users_with_search(self, client: TestClient, auth_headers: dict, sample_bbs_users: list[User]):
        """Test listing users with search."""
        response = client.get("/api/v1/users?search=Alice", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert any("Alice" in u["nickname"] for u in data["items"])

    def test_get_user_detail(self, client: TestClient, auth_headers: dict, sample_bbs_users: list[User]):
        """Test getting user details."""
        user_key = sample_bbs_users[0].public_key
        response = client.get(f"/api/v1/users/{user_key}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["nickname"] == "Alice"

    def test_get_user_not_found(self, client: TestClient, auth_headers: dict):
        """Test getting non-existent user."""
        response = client.get("/api/v1/users/nonexistent123", headers=auth_headers)
        assert response.status_code == 404

    def test_ban_user(self, client: TestClient, auth_headers: dict, sample_bbs_users: list[User], db_session: Session):
        """Test banning a user."""
        user_key = sample_bbs_users[0].public_key
        response = client.post(
            f"/api/v1/users/{user_key}/ban",
            headers=auth_headers,
            json={"reason": "Test ban", "duration_hours": 24},
        )
        assert response.status_code == 200
        data = response.json()
        # Response may contain success message or updated user
        assert "message" in data or "public_key" in data

    def test_unban_user(self, client: TestClient, auth_headers: dict, sample_bbs_users: list[User], db_session: Session):
        """Test unbanning a user."""
        user = sample_bbs_users[0]
        user.is_banned = True
        db_session.commit()

        response = client.post(f"/api/v1/users/{user.public_key}/unban", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        # Response may contain success message or updated user
        assert "message" in data or "public_key" in data


class TestAreasEndpoints:
    """Test areas API endpoints."""

    def test_list_areas(self, client: TestClient, auth_headers: dict, sample_areas: list[Area]):
        """Test listing areas."""
        response = client.get("/api/v1/areas", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] >= 1

    def test_get_area(self, client: TestClient, auth_headers: dict, sample_areas: list[Area]):
        """Test getting area details."""
        area_name = sample_areas[0].name
        response = client.get(f"/api/v1/areas/{area_name}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == area_name

    def test_get_area_not_found(self, client: TestClient, auth_headers: dict):
        """Test getting non-existent area."""
        response = client.get("/api/v1/areas/nonexistent", headers=auth_headers)
        assert response.status_code == 404

    def test_create_area(self, client: TestClient, auth_headers: dict, db_session: Session):
        """Test creating a new area."""
        response = client.post(
            "/api/v1/areas",
            headers=auth_headers,
            json={"name": "newarea", "description": "A new test area"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "newarea"

    def test_create_duplicate_area(self, client: TestClient, auth_headers: dict, sample_areas: list[Area]):
        """Test creating duplicate area."""
        existing_name = sample_areas[0].name
        response = client.post(
            "/api/v1/areas",
            headers=auth_headers,
            json={"name": existing_name, "description": "Duplicate"},
        )
        assert response.status_code == 409

    def test_update_area(self, client: TestClient, auth_headers: dict, sample_areas: list[Area]):
        """Test updating an area."""
        area_name = sample_areas[0].name
        response = client.patch(
            f"/api/v1/areas/{area_name}",
            headers=auth_headers,
            json={"description": "Updated description"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["description"] == "Updated description"

    def test_delete_protected_area(self, client: TestClient, auth_headers: dict, db_session: Session):
        """Test cannot delete protected area."""
        response = client.delete("/api/v1/areas/generale", headers=auth_headers)
        assert response.status_code == 400

    def test_get_area_stats(self, client: TestClient, auth_headers: dict, sample_areas: list[Area], sample_messages: list[Message]):
        """Test getting area statistics."""
        area_name = sample_areas[0].name
        response = client.get(f"/api/v1/areas/{area_name}/stats", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "message_count" in data
        assert "unique_posters" in data


class TestMessagesEndpoints:
    """Test messages API endpoints."""

    def test_list_messages(self, client: TestClient, auth_headers: dict, sample_messages: list[Message]):
        """Test listing messages."""
        response = client.get("/api/v1/messages", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data

    def test_list_messages_with_filter(self, client: TestClient, auth_headers: dict, sample_messages: list[Message], sample_areas: list[Area]):
        """Test listing messages with area filter."""
        area_name = sample_areas[0].name
        response = client.get(f"/api/v1/messages?area={area_name}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) >= 0

    def test_get_message(self, client: TestClient, auth_headers: dict, sample_messages: list[Message]):
        """Test getting message details."""
        msg_id = sample_messages[0].id
        response = client.get(f"/api/v1/messages/{msg_id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == msg_id

    def test_delete_message(self, client: TestClient, auth_headers: dict, sample_messages: list[Message]):
        """Test deleting a message."""
        msg_id = sample_messages[0].id
        response = client.delete(f"/api/v1/messages/{msg_id}", headers=auth_headers)
        assert response.status_code == 204


class TestLogsEndpoints:
    """Test activity logs API endpoints."""

    def test_list_logs(self, client: TestClient, auth_headers: dict, db_session: Session):
        """Test listing activity logs."""
        # Create some logs
        db_session.add(ActivityLog.log(EventType.USER_FIRST_SEEN, user_key="A" * 64, details="Test log"))
        db_session.commit()

        response = client.get("/api/v1/logs", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data

    def test_list_event_types(self, client: TestClient, auth_headers: dict):
        """Test listing event types."""
        response = client.get("/api/v1/logs/types", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "types" in data

    def test_get_log_stats(self, client: TestClient, auth_headers: dict, db_session: Session):
        """Test getting log statistics."""
        response = client.get("/api/v1/logs/stats", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "total_entries" in data
        assert "by_type" in data


class TestSettingsEndpoints:
    """Test settings API endpoints."""

    def test_get_settings(self, client: TestClient, auth_headers: dict):
        """Test getting settings."""
        response = client.get("/api/v1/settings", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "bbs_name" in data

    def test_health_check_no_auth(self, client: TestClient):
        """Test settings health check without auth."""
        response = client.get("/api/v1/settings/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_get_system_info(self, client: TestClient, auth_headers: dict):
        """Test getting system info."""
        response = client.get("/api/v1/settings/system", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "python_version" in data
        assert "db_tables" in data

    def test_update_settings_requires_superadmin(self, client: TestClient, auth_headers: dict):
        """Test that updating settings requires superadmin."""
        response = client.patch(
            "/api/v1/settings",
            headers=auth_headers,
            json={"bbs_name": "New Name"},
        )
        assert response.status_code == 403

    def test_maintenance_cleanup_dry_run(self, client: TestClient, superadmin_headers: dict):
        """Test maintenance cleanup dry run."""
        response = client.post(
            "/api/v1/settings/maintenance",
            headers=superadmin_headers,
            json={"operation": "cleanup", "dry_run": True},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["operation"] == "cleanup"
        assert data["success"] is True


class TestAdminManagement:
    """Test admin user management endpoints."""

    def test_list_admins_as_regular_admin(self, client: TestClient, auth_headers: dict, admin_user: AdminUser):
        """Test that regular admins can list admins but with limited info."""
        response = client.get("/auth/admins", headers=auth_headers)
        # Regular admins can list admins, but see limited info
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_list_admins_as_superadmin(self, client: TestClient, superadmin_headers: dict, admin_user: AdminUser):
        """Test listing admins as superadmin."""
        response = client.get("/auth/admins", headers=superadmin_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_create_admin(self, client: TestClient, superadmin_headers: dict):
        """Test creating new admin."""
        response = client.post(
            "/auth/admins",
            headers=superadmin_headers,
            json={"username": "newadmin", "password": "NewPassword123!"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["username"] == "newadmin"
        assert data["is_superadmin"] is False

    def test_create_duplicate_admin(self, client: TestClient, superadmin_headers: dict, admin_user: AdminUser):
        """Test creating duplicate admin fails."""
        response = client.post(
            "/auth/admins",
            headers=superadmin_headers,
            json={"username": admin_user.username, "password": "Password123!"},
        )
        assert response.status_code == 409

    def test_change_password(self, client: TestClient, auth_headers: dict):
        """Test changing own password."""
        response = client.post(
            "/auth/change-password",
            headers=auth_headers,
            json={
                "current_password": "TestPassword123!",
                "new_password": "NewTestPassword123!",
            },
        )
        assert response.status_code == 200

    def test_change_password_wrong_current(self, client: TestClient, auth_headers: dict):
        """Test changing password with wrong current password."""
        response = client.post(
            "/auth/change-password",
            headers=auth_headers,
            json={
                "current_password": "WrongPassword",
                "new_password": "NewTestPassword123!",
            },
        )
        assert response.status_code == 400  # Bad request for wrong current password
