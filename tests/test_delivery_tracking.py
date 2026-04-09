"""
Tests for Message Delivery Tracking.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

import pytest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

# Add src to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from bbs.models.base import Base
from bbs.models.delivery_status import DeliveryStatus, DeliveryState
from bbs.services.delivery_tracker import DeliveryTracker


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session


@pytest.fixture
def tracker(db_session):
    """Create a DeliveryTracker instance."""
    return DeliveryTracker(
        session_factory=db_session,
        default_max_retries=3,
        retry_delay_seconds=30,
        pending_timeout_seconds=60,
    )


class TestDeliveryStatusModel:
    """Test DeliveryStatus model."""

    def test_delivery_state_enum(self):
        """Test DeliveryState enum values."""
        assert DeliveryState.PENDING.value == "pending"
        assert DeliveryState.SENDING.value == "sending"
        assert DeliveryState.SENT.value == "sent"
        assert DeliveryState.DELIVERED.value == "delivered"
        assert DeliveryState.READ.value == "read"
        assert DeliveryState.FAILED.value == "failed"

    def test_create_delivery_status(self, db_session):
        """Test creating a delivery status record."""
        session = db_session()
        delivery = DeliveryStatus(
            message_type="private",
            message_id=123,
            sender_key="ABC123" + "0" * 58,
            recipient_key="DEF456" + "0" * 58,
        )
        session.add(delivery)
        session.commit()

        assert delivery.id is not None
        assert delivery.state == DeliveryState.PENDING
        assert delivery.retry_count == 0
        session.close()

    def test_mark_sending(self, db_session):
        """Test marking as sending."""
        session = db_session()
        delivery = DeliveryStatus(
            message_type="private",
            message_id=1,
            sender_key="ABC" + "0" * 61,
        )
        session.add(delivery)
        session.commit()

        delivery.mark_sending()
        assert delivery.state == DeliveryState.SENDING
        session.close()

    def test_mark_sent(self, db_session):
        """Test marking as sent."""
        session = db_session()
        delivery = DeliveryStatus(
            message_type="private",
            message_id=1,
            sender_key="ABC" + "0" * 61,
        )
        session.add(delivery)
        session.commit()

        delivery.mark_sent("ext123")
        assert delivery.state == DeliveryState.SENT
        assert delivery.external_id == "ext123"
        assert delivery.sent_at is not None
        session.close()

    def test_mark_delivered(self, db_session):
        """Test marking as delivered."""
        session = db_session()
        delivery = DeliveryStatus(
            message_type="private",
            message_id=1,
            sender_key="ABC" + "0" * 61,
        )
        session.add(delivery)
        session.commit()

        delivery.mark_delivered(hops=3, rssi=-80)
        assert delivery.state == DeliveryState.DELIVERED
        assert delivery.delivered_at is not None
        assert delivery.ack_hops == 3
        assert delivery.ack_rssi == -80
        session.close()

    def test_mark_read(self, db_session):
        """Test marking as read."""
        session = db_session()
        delivery = DeliveryStatus(
            message_type="private",
            message_id=1,
            sender_key="ABC" + "0" * 61,
        )
        session.add(delivery)
        session.commit()

        delivery.mark_read()
        assert delivery.state == DeliveryState.READ
        assert delivery.read_at is not None
        session.close()

    def test_mark_failed(self, db_session):
        """Test marking as failed."""
        session = db_session()
        delivery = DeliveryStatus(
            message_type="private",
            message_id=1,
            sender_key="ABC" + "0" * 61,
        )
        session.add(delivery)
        session.commit()

        delivery.mark_failed("Network timeout")
        assert delivery.state == DeliveryState.FAILED
        assert delivery.failed_at is not None
        assert delivery.error_message == "Network timeout"
        session.close()

    def test_increment_retry(self, db_session):
        """Test retry counter."""
        session = db_session()
        delivery = DeliveryStatus(
            message_type="private",
            message_id=1,
            sender_key="ABC" + "0" * 61,
            max_retries=3,
        )
        session.add(delivery)
        session.commit()

        assert delivery.increment_retry() is True  # 1 < 3
        assert delivery.retry_count == 1
        assert delivery.increment_retry() is True  # 2 < 3
        assert delivery.retry_count == 2
        assert delivery.increment_retry() is False  # 3 >= 3
        assert delivery.retry_count == 3
        session.close()

    def test_is_properties(self, db_session):
        """Test is_* properties."""
        session = db_session()
        delivery = DeliveryStatus(
            message_type="private",
            message_id=1,
            sender_key="ABC" + "0" * 61,
        )
        session.add(delivery)
        session.commit()

        assert delivery.is_pending is True
        assert delivery.is_delivered is False
        assert delivery.is_failed is False

        delivery.mark_delivered()
        assert delivery.is_pending is False
        assert delivery.is_delivered is True
        session.close()

    def test_can_retry(self, db_session):
        """Test can_retry property."""
        session = db_session()
        delivery = DeliveryStatus(
            message_type="private",
            message_id=1,
            sender_key="ABC" + "0" * 61,
            max_retries=2,
        )
        session.add(delivery)
        session.commit()

        # Can't retry if not failed
        assert delivery.can_retry is False

        delivery.mark_failed("Error")
        assert delivery.can_retry is True

        delivery.retry_count = 2
        assert delivery.can_retry is False
        session.close()

    def test_delivery_time_ms(self, db_session):
        """Test delivery time calculation."""
        session = db_session()
        delivery = DeliveryStatus(
            message_type="private",
            message_id=1,
            sender_key="ABC" + "0" * 61,
        )
        session.add(delivery)
        session.commit()

        assert delivery.delivery_time_ms is None

        delivery.sent_at = datetime.utcnow()
        delivery.delivered_at = delivery.sent_at + timedelta(milliseconds=500)
        # Allow some tolerance
        assert 490 <= delivery.delivery_time_ms <= 510
        session.close()

    def test_repr(self, db_session):
        """Test string representation."""
        session = db_session()
        delivery = DeliveryStatus(
            message_type="private",
            message_id=123,
            sender_key="ABC" + "0" * 61,
        )
        session.add(delivery)
        session.commit()

        repr_str = repr(delivery)
        assert "DeliveryStatus" in repr_str
        assert "private:123" in repr_str
        assert "pending" in repr_str
        session.close()


class TestDeliveryTracker:
    """Test DeliveryTracker service."""

    def test_create_delivery(self, tracker, db_session):
        """Test creating a delivery through tracker."""
        delivery = tracker.create_delivery(
            message_type="private",
            message_id=100,
            sender_key="SENDER" + "0" * 58,
            recipient_key="RECIPIENT" + "0" * 55,
        )

        assert delivery.id is not None
        assert delivery.message_type == "private"
        assert delivery.message_id == 100
        assert delivery.state == DeliveryState.PENDING

    def test_mark_sending_through_tracker(self, tracker):
        """Test marking as sending through tracker."""
        delivery = tracker.create_delivery(
            message_type="public",
            message_id=1,
            sender_key="ABC" + "0" * 61,
        )

        updated = tracker.mark_sending(delivery.id)
        assert updated.state == DeliveryState.SENDING

    def test_mark_sent_through_tracker(self, tracker):
        """Test marking as sent through tracker."""
        delivery = tracker.create_delivery(
            message_type="public",
            message_id=1,
            sender_key="ABC" + "0" * 61,
        )

        updated = tracker.mark_sent(delivery.id, external_id="mesh123")
        assert updated.state == DeliveryState.SENT
        assert updated.external_id == "mesh123"

    def test_process_ack(self, tracker):
        """Test ACK processing."""
        delivery = tracker.create_delivery(
            message_type="private",
            message_id=1,
            sender_key="ABC" + "0" * 61,
        )
        tracker.mark_sent(delivery.id, external_id="ack_test_123")

        updated = tracker.process_ack("ack_test_123", hops=2, rssi=-75)
        assert updated is not None
        assert updated.state == DeliveryState.DELIVERED
        assert updated.ack_hops == 2
        assert updated.ack_rssi == -75

    def test_process_ack_unknown_message(self, tracker):
        """Test ACK for unknown message returns None."""
        result = tracker.process_ack("unknown_id")
        assert result is None

    def test_mark_failed_through_tracker(self, tracker):
        """Test marking as failed through tracker."""
        delivery = tracker.create_delivery(
            message_type="broadcast",
            message_id=1,
            sender_key="ABC" + "0" * 61,
        )

        updated = tracker.mark_failed(delivery.id, "Timeout")
        assert updated.state == DeliveryState.FAILED
        assert updated.error_message == "Timeout"

    def test_retry_delivery(self, tracker):
        """Test retry logic."""
        delivery = tracker.create_delivery(
            message_type="private",
            message_id=1,
            sender_key="ABC" + "0" * 61,
            max_retries=3,  # Allow 3 retries
        )
        tracker.mark_failed(delivery.id, "First failure")

        # First retry (retry_count becomes 1)
        updated = tracker.retry_delivery(delivery.id)
        assert updated.state == DeliveryState.PENDING
        assert updated.retry_count == 1

        # Second failure and retry (retry_count becomes 2)
        tracker.mark_failed(delivery.id, "Second failure")
        updated = tracker.retry_delivery(delivery.id)
        assert updated.state == DeliveryState.PENDING
        assert updated.retry_count == 2

        # Third failure and retry (retry_count becomes 3, equals max_retries)
        tracker.mark_failed(delivery.id, "Third failure")
        updated = tracker.retry_delivery(delivery.id)
        # Now retry_count (3) >= max_retries (3), so increment_retry returns False
        # and mark_failed is called
        assert updated.state == DeliveryState.FAILED
        assert "Max retries" in updated.error_message

    def test_get_delivery(self, tracker):
        """Test getting delivery by ID."""
        delivery = tracker.create_delivery(
            message_type="private",
            message_id=1,
            sender_key="ABC" + "0" * 61,
        )

        found = tracker.get_delivery(delivery.id)
        assert found is not None
        assert found.id == delivery.id

    def test_get_delivery_not_found(self, tracker):
        """Test getting non-existent delivery."""
        found = tracker.get_delivery(9999)
        assert found is None

    def test_get_delivery_by_message(self, tracker):
        """Test getting delivery by message reference."""
        delivery = tracker.create_delivery(
            message_type="private",
            message_id=42,
            sender_key="ABC" + "0" * 61,
        )

        found = tracker.get_delivery_by_message("private", 42)
        assert found is not None
        assert found.id == delivery.id

    def test_get_pending_deliveries(self, tracker):
        """Test getting pending deliveries."""
        # Create some deliveries in different states
        d1 = tracker.create_delivery("private", 1, "A" * 64)
        d2 = tracker.create_delivery("private", 2, "B" * 64)
        d3 = tracker.create_delivery("private", 3, "C" * 64)

        tracker.mark_sending(d1.id)
        tracker.mark_sent(d2.id)
        tracker.mark_sent(d3.id, "ext123")
        tracker.process_ack("ext123")  # d3 delivered

        pending = tracker.get_pending_deliveries()
        pending_ids = [d.id for d in pending]

        assert d1.id in pending_ids  # SENDING is pending
        assert d2.id not in pending_ids  # SENT is not pending (we check PENDING/SENDING)
        assert d3.id not in pending_ids  # DELIVERED

    def test_get_delivery_stats(self, tracker):
        """Test getting delivery statistics."""
        tracker.create_delivery("private", 1, "A" * 64)
        tracker.create_delivery("private", 2, "B" * 64)
        d3 = tracker.create_delivery("private", 3, "C" * 64)
        tracker.mark_failed(d3.id, "Error")

        stats = tracker.get_delivery_stats()
        assert stats["pending"] == 2
        assert stats["failed"] == 1

    def test_on_delivered_callback(self, tracker):
        """Test delivery callback is triggered."""
        callback_results = []

        def on_delivered(delivery):
            callback_results.append(delivery.id)

        tracker.on_delivered(on_delivered)

        delivery = tracker.create_delivery("private", 1, "A" * 64)
        tracker.mark_sent(delivery.id, "cb_test")
        tracker.process_ack("cb_test")

        assert delivery.id in callback_results

    def test_on_failed_callback(self, tracker):
        """Test failure callback is triggered."""
        callback_results = []

        def on_failed(delivery):
            callback_results.append(delivery.id)

        tracker.on_failed(on_failed)

        delivery = tracker.create_delivery("private", 1, "A" * 64)
        tracker.mark_failed(delivery.id, "Test error")

        assert delivery.id in callback_results

    def test_cleanup_old_records(self, tracker, db_session):
        """Test cleaning up old records."""
        # Create a delivery
        delivery = tracker.create_delivery("private", 1, "A" * 64)

        # Manually set created_at to old date
        session = db_session()
        d = session.query(DeliveryStatus).filter_by(id=delivery.id).first()
        d.created_at = datetime.utcnow() - timedelta(days=60)
        session.commit()
        session.close()

        # Cleanup records older than 30 days
        deleted = tracker.cleanup_old_records(days=30)
        assert deleted == 1

        # Verify it's gone
        assert tracker.get_delivery(delivery.id) is None


class TestDeliveryTrackerEdgeCases:
    """Test edge cases for DeliveryTracker."""

    def test_mark_nonexistent_delivery(self, tracker):
        """Test marking non-existent delivery returns None."""
        assert tracker.mark_sending(9999) is None
        assert tracker.mark_sent(9999) is None
        assert tracker.mark_failed(9999, "Error") is None

    def test_retry_non_failed_delivery(self, tracker):
        """Test retry on non-failed delivery."""
        delivery = tracker.create_delivery("private", 1, "A" * 64)
        # Can't retry pending (not failed)
        result = tracker.retry_delivery(delivery.id)
        assert result is not None
        assert result.state == DeliveryState.PENDING  # Unchanged

    def test_multiple_acks_same_message(self, tracker):
        """Test handling duplicate ACKs."""
        delivery = tracker.create_delivery("private", 1, "A" * 64)
        tracker.mark_sent(delivery.id, "dup_test")

        # First ACK
        result1 = tracker.process_ack("dup_test", hops=1)
        assert result1 is not None

        # Second ACK (should return None - already removed from pending)
        result2 = tracker.process_ack("dup_test", hops=2)
        assert result2 is None

    def test_callback_error_handling(self, tracker):
        """Test that callback errors don't break processing."""
        def bad_callback(delivery):
            raise Exception("Callback error")

        tracker.on_delivered(bad_callback)

        delivery = tracker.create_delivery("private", 1, "A" * 64)
        tracker.mark_sent(delivery.id, "err_test")

        # Should not raise
        result = tracker.process_ack("err_test")
        assert result is not None
        assert result.state == DeliveryState.DELIVERED


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
