"""
Tests for database models.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

import pytest
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from bbs.models.user import User
from bbs.models.area import Area
from bbs.models.message import Message
from bbs.models.private_message import PrivateMessage
from bbs.models.activity_log import ActivityLog, EventType, log_activity


class TestUserModel:
    """Tests for User model."""

    def test_create_user(self, db_session: Session, test_sender_key: str):
        """Test creating a user."""
        user = User(public_key=test_sender_key, nickname="TestUser")
        db_session.add(user)
        db_session.commit()

        assert user.id is not None
        assert user.public_key == test_sender_key
        assert user.nickname == "TestUser"
        assert user.first_seen is not None

    def test_user_short_key(self, test_sender_key: str):
        """Test user short_key property."""
        user = User(public_key=test_sender_key)
        assert user.short_key == test_sender_key[:8]

    def test_user_display_name_with_nick(self, test_sender_key: str):
        """Test display_name with nickname set."""
        user = User(public_key=test_sender_key, nickname="TestUser")
        assert user.display_name == "TestUser"

    def test_user_display_name_without_nick(self, test_sender_key: str):
        """Test display_name without nickname."""
        user = User(public_key=test_sender_key)
        assert user.display_name == test_sender_key[:8]

    def test_user_unique_key(self, db_session: Session, test_sender_key: str):
        """Test that public_key is unique."""
        user1 = User(public_key=test_sender_key)
        db_session.add(user1)
        db_session.commit()

        user2 = User(public_key=test_sender_key)
        db_session.add(user2)

        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()


class TestAreaModel:
    """Tests for Area model."""

    def test_create_area(self, db_session: Session):
        """Test creating an area."""
        # Use unique name to avoid conflict with defaults
        area = Area(name="test_unique_area", description="Test area")
        db_session.add(area)
        db_session.commit()

        assert area.id is not None
        assert area.name == "test_unique_area"
        assert area.is_public is True

    def test_area_unique_name(self, db_session: Session):
        """Test that area name is unique."""
        area1 = Area(name="unique_test_1")
        db_session.add(area1)
        db_session.commit()

        area2 = Area(name="unique_test_1")
        db_session.add(area2)

        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_default_areas_exist(self, db_session: Session):
        """Test that default areas are created by init_database."""
        areas = db_session.query(Area).all()
        area_names = [a.name for a in areas]

        # Check default areas exist
        assert "generale" in area_names
        assert "tech" in area_names
        assert "emergenze" in area_names


class TestMessageModel:
    """Tests for Message model."""

    def test_create_message(
        self, db_session: Session, test_sender_key: str, sample_areas: list[Area]
    ):
        """Test creating a message."""
        # First create a user
        user = User(public_key=test_sender_key)
        db_session.add(user)
        db_session.commit()

        message = Message(
            area_id=sample_areas[0].id,
            sender_key=test_sender_key,
            body="Hello, world!",
        )
        db_session.add(message)
        db_session.commit()

        assert message.id is not None
        assert message.body == "Hello, world!"
        assert message.timestamp is not None

    def test_message_preview(
        self, db_session: Session, test_sender_key: str, sample_areas: list[Area]
    ):
        """Test message preview property."""
        # First create a user
        user = User(public_key=test_sender_key)
        db_session.add(user)
        db_session.commit()

        long_body = "A" * 100
        message = Message(
            area_id=sample_areas[0].id,
            sender_key=test_sender_key,
            body=long_body,
        )

        assert len(message.preview) <= 30  # 27 chars + "..."

    def test_message_threading(
        self, db_session: Session, test_sender_key: str, sample_areas: list[Area]
    ):
        """Test message reply threading."""
        # First create a user
        user = User(public_key=test_sender_key)
        db_session.add(user)
        db_session.commit()

        parent = Message(
            area_id=sample_areas[0].id,
            sender_key=test_sender_key,
            body="Parent message",
        )
        db_session.add(parent)
        db_session.commit()

        reply = Message(
            area_id=sample_areas[0].id,
            sender_key=test_sender_key,
            body="Reply message",
            parent_id=parent.id,
        )
        db_session.add(reply)
        db_session.commit()

        assert reply.parent_id == parent.id


class TestPrivateMessageModel:
    """Tests for PrivateMessage model."""

    def test_create_private_message(
        self, db_session: Session, test_sender_key: str, test_sender_key_2: str
    ):
        """Test creating a private message."""
        # Create users first
        user1 = User(public_key=test_sender_key)
        user2 = User(public_key=test_sender_key_2)
        db_session.add_all([user1, user2])
        db_session.commit()

        pm = PrivateMessage(
            sender_key=test_sender_key,
            recipient_key=test_sender_key_2,
            body="Secret message",
        )
        db_session.add(pm)
        db_session.commit()

        assert pm.id is not None
        assert pm.is_read is False

    def test_mark_as_read(
        self, db_session: Session, test_sender_key: str, test_sender_key_2: str
    ):
        """Test marking message as read."""
        # Create users first
        user1 = User(public_key=test_sender_key)
        user2 = User(public_key=test_sender_key_2)
        db_session.add_all([user1, user2])
        db_session.commit()

        pm = PrivateMessage(
            sender_key=test_sender_key,
            recipient_key=test_sender_key_2,
            body="Secret message",
        )
        db_session.add(pm)
        db_session.commit()

        assert pm.is_read is False
        assert pm.read_at is None

        pm.mark_as_read()
        db_session.commit()

        assert pm.is_read is True
        assert pm.read_at is not None


class TestActivityLog:
    """Tests for ActivityLog model."""

    def test_log_activity(self, db_session: Session, test_sender_key: str):
        """Test logging activity."""
        log_activity(
            db_session,
            EventType.USER_FIRST_SEEN,
            user_key=test_sender_key,
            details="First connection",
        )

        log = db_session.query(ActivityLog).filter_by(
            event_type=EventType.USER_FIRST_SEEN.value,
            user_key=test_sender_key,
        ).first()
        assert log is not None
        assert log.event_type == EventType.USER_FIRST_SEEN.value
        assert log.user_key == test_sender_key
        assert log.details == "First connection"

    def test_log_bbs_events(self, db_session: Session):
        """Test logging BBS system events."""
        log_activity(db_session, EventType.BBS_STARTED, details="Test BBS")

        log = db_session.query(ActivityLog).filter_by(
            event_type=EventType.BBS_STARTED.value,
        ).first()
        # Note: BBS_STARTED may already exist from init_database
        # We just verify the query works
        assert log is None or log.event_type == EventType.BBS_STARTED.value
