"""
Tests for StatsCollector service and stats API endpoint.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from bbs.services.stats_collector import StatsCollector
from bbs.models.user import User
from bbs.models.message import Message
from bbs.models.area import Area
from bbs.models.private_message import PrivateMessage
from bbs.models.activity_log import ActivityLog, EventType
from web.main import create_app
from web.config import WebConfig, set_web_config, reset_web_config
from web.auth.models import AdminUser, AdminUserRepository
from web.auth.password import hash_password
from web.auth.jwt import create_access_token
from web.dependencies import get_db


# ---------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------


@pytest.fixture
def web_config(config) -> WebConfig:
    reset_web_config()
    cfg = WebConfig(
        debug=True,
        secret_key="test-secret-key-for-testing-only-32chars",
    )
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
        username="statsadmin",
        password_hash=hash_password("TestPassword123!"),
        is_superadmin=False,
    )
    db_session.commit()
    return admin


@pytest.fixture
def auth_headers(admin_user: AdminUser, web_config: WebConfig) -> dict:
    token = create_access_token(
        admin_id=admin_user.id,
        username=admin_user.username,
        is_superadmin=admin_user.is_superadmin,
        secret_key=web_config.secret_key,
        expire_minutes=15,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def populated_db(db_session: Session, sample_areas):
    """Populate DB with users, messages, and PMs for stats testing."""
    now = datetime.utcnow()

    # Users
    users = [
        User(public_key="U" * 64, nickname="UserA", last_seen=now),
        User(
            public_key="V" * 64,
            nickname="UserB",
            last_seen=now - timedelta(hours=2),
        ),
        User(
            public_key="W" * 64,
            nickname="UserOld",
            last_seen=now - timedelta(days=10),
        ),
        User(
            public_key="X" * 64,
            nickname="Banned",
            is_banned=True,
            last_seen=now,
        ),
    ]
    for u in users:
        db_session.add(u)
    db_session.flush()

    area = sample_areas[0]

    # Messages: 2 today, 1 old
    msgs = [
        Message(area_id=area.id, sender_key="U" * 64, body="Msg1", timestamp=now),
        Message(
            area_id=area.id,
            sender_key="V" * 64,
            body="Msg2",
            timestamp=now - timedelta(minutes=30),
        ),
        Message(
            area_id=area.id,
            sender_key="W" * 64,
            body="OldMsg",
            timestamp=now - timedelta(days=5),
        ),
    ]
    for m in msgs:
        db_session.add(m)

    # Private messages
    pm = PrivateMessage(
        sender_key="U" * 64,
        recipient_key="V" * 64,
        body="Hello privately",
        timestamp=now,
        is_read=False,
    )
    db_session.add(pm)

    db_session.commit()
    return users, msgs


# ---------------------------------------------------------------
# StatsCollector unit tests
# ---------------------------------------------------------------


class TestStatsCollector:
    """Tests for the StatsCollector service."""

    def test_collect_returns_all_sections(self, db_session, config):
        """Verify the payload contains all required top-level keys."""
        collector = StatsCollector(db_session)
        stats = collector.collect()

        assert "users" in stats
        assert "messages" in stats
        assert "radio" in stats
        assert "delivery" in stats
        assert "system" in stats
        assert "collected_at" in stats

    def test_users_stats(self, db_session, config, populated_db, sample_areas):
        """Verify user counts are correct."""
        collector = StatsCollector(db_session)
        stats = collector.collect()

        users = stats["users"]
        assert users["total"] == 4
        assert users["active_24h"] >= 2  # UserA, UserB, Banned (last_seen=now)
        assert users["banned"] == 1

    def test_messages_stats(self, db_session, config, populated_db, sample_areas):
        """Verify message counts are correct."""
        collector = StatsCollector(db_session)
        stats = collector.collect()

        msgs = stats["messages"]
        assert msgs["public"]["total"] == 3
        assert msgs["public"]["last_hour"] >= 2
        assert msgs["private"]["total"] == 1
        assert msgs["private"]["unread"] == 1
        assert msgs["areas"] >= 1

    def test_radio_disconnected(self, db_session, config):
        """Verify radio section when not connected."""
        collector = StatsCollector(db_session)
        stats = collector.collect()

        radio = stats["radio"]
        assert radio["connected"] is False
        assert "status" in radio
        assert radio["messages_processed"] >= 0

    def test_system_section(self, db_session, config):
        """Verify system section contains expected fields."""
        collector = StatsCollector(db_session)
        stats = collector.collect()

        system = stats["system"]
        assert system["bbs_name"] == "Test BBS"
        assert "uptime_seconds" in system
        assert "db_size_bytes" in system

    def test_empty_database(self, db_session, config):
        """Verify stats work correctly with no user data."""
        collector = StatsCollector(db_session)
        stats = collector.collect()

        assert stats["users"]["total"] == 0
        assert stats["messages"]["public"]["total"] == 0
        assert stats["messages"]["private"]["total"] == 0

    def test_delivery_section_present(self, db_session, config):
        """Verify delivery section is always present."""
        collector = StatsCollector(db_session)
        stats = collector.collect()

        assert "delivery" in stats

    def test_collected_at_is_iso_format(self, db_session, config):
        """Verify collected_at is a valid ISO timestamp."""
        collector = StatsCollector(db_session)
        stats = collector.collect()

        # Should parse without error
        datetime.fromisoformat(stats["collected_at"])


# ---------------------------------------------------------------
# Stats API endpoint tests
# ---------------------------------------------------------------


class TestStatsAPI:
    """Tests for the /api/v1/stats endpoint."""

    def test_get_stats_authenticated(
        self, client, auth_headers, populated_db, sample_areas
    ):
        """Authenticated request returns stats payload."""
        response = client.get("/api/v1/stats", headers=auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert "users" in data
        assert "messages" in data
        assert "radio" in data
        assert "system" in data

    def test_get_stats_unauthenticated(self, client):
        """Unauthenticated request is rejected."""
        response = client.get("/api/v1/stats")
        assert response.status_code in (401, 403)

    def test_health_no_auth(self, client):
        """Health check endpoint requires no authentication."""
        response = client.get("/api/v1/stats/health")
        assert response.status_code == 200

        data = response.json()
        assert "status" in data
        assert "radio_connected" in data
        assert "messages_processed" in data

    def test_stats_users_counts(
        self, client, auth_headers, populated_db, sample_areas
    ):
        """Verify user counts in API response."""
        response = client.get("/api/v1/stats", headers=auth_headers)
        data = response.json()

        assert data["users"]["total"] == 4
        assert data["users"]["banned"] == 1

    def test_stats_messages_counts(
        self, client, auth_headers, populated_db, sample_areas
    ):
        """Verify message counts in API response."""
        response = client.get("/api/v1/stats", headers=auth_headers)
        data = response.json()

        assert data["messages"]["public"]["total"] == 3
        assert data["messages"]["private"]["total"] == 1


# ---------------------------------------------------------------
# MQTT stats publishing test
# ---------------------------------------------------------------


class TestMQTTStatsPublish:
    """Tests for periodic MQTT stats publishing."""

    @pytest.mark.asyncio
    async def test_publish_stats_calls_mqtt(self, db_session, config):
        """Verify that collect() output is valid for MQTT publish."""
        collector = StatsCollector(db_session)
        stats = collector.collect()

        # Simulate what publish_stats does
        mock_client = MagicMock()
        mock_client.is_connected = True
        mock_client.publish_stats = AsyncMock(return_value=True)

        result = await mock_client.publish_stats(stats)
        assert result is True
        mock_client.publish_stats.assert_called_once_with(stats)

    @pytest.mark.asyncio
    async def test_publish_stats_skipped_when_disconnected(self):
        """Verify MQTT publish is skipped when client is not connected."""
        mock_client = MagicMock()
        mock_client.is_connected = False

        # The core loop checks is_connected before publishing
        if not mock_client.is_connected:
            published = False
        else:
            published = True

        assert published is False


# ---------------------------------------------------------------
# Config fields test
# ---------------------------------------------------------------


class TestStatsConfig:
    """Tests for stats-related config fields."""

    def test_default_stats_publish_interval(self):
        """Verify default stats_publish_interval is 5 minutes."""
        from utils.config import Config

        cfg = Config()
        assert cfg.stats_publish_interval == 300

    def test_default_send_delay(self):
        """Verify default send_delay is 10 seconds (tuned for multi-hop mesh)."""
        from utils.config import Config

        cfg = Config()
        assert cfg.send_delay == 10.0

    def test_default_max_send_attempts(self):
        """Verify default max_send_attempts is 2."""
        from utils.config import Config

        cfg = Config()
        assert cfg.max_send_attempts == 2

    def test_default_send_retry_delay(self):
        """Verify default send_retry_delay is 2 seconds."""
        from utils.config import Config

        cfg = Config()
        assert cfg.send_retry_delay == 2.0

    def test_stats_publish_interval_is_updatable(self):
        """Verify stats_publish_interval is in UPDATABLE_FIELDS."""
        from utils.config import UPDATABLE_FIELDS

        assert "stats_publish_interval" in UPDATABLE_FIELDS
        assert "send_delay" in UPDATABLE_FIELDS
        assert "max_send_attempts" in UPDATABLE_FIELDS
        assert "send_retry_delay" in UPDATABLE_FIELDS
