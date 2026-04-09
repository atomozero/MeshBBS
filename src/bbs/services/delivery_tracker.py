"""
Message delivery tracking service for MeshCore BBS.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Callable, Any

from sqlalchemy.orm import Session

from ..models.delivery_status import DeliveryStatus, DeliveryState


logger = logging.getLogger(__name__)


class DeliveryTracker:
    """
    Service for tracking message delivery through the MeshCore network.

    Manages delivery status records, handles ACK processing, and provides
    retry logic for failed deliveries.
    """

    def __init__(
        self,
        session_factory: Callable[[], Session],
        default_max_retries: int = 3,
        retry_delay_seconds: int = 30,
        pending_timeout_seconds: int = 120,
    ):
        """
        Initialize the delivery tracker.

        Args:
            session_factory: Callable that returns a new database session
            default_max_retries: Default number of retries for failed messages
            retry_delay_seconds: Delay between retry attempts
            pending_timeout_seconds: Time before a pending message is considered stale
        """
        self._session_factory = session_factory
        self._default_max_retries = default_max_retries
        self._retry_delay_seconds = retry_delay_seconds
        self._pending_timeout_seconds = pending_timeout_seconds

        # Callbacks for delivery events
        self._on_delivered_callbacks: List[Callable[[DeliveryStatus], Any]] = []
        self._on_failed_callbacks: List[Callable[[DeliveryStatus], Any]] = []

        # Pending ACKs tracking (external_id -> DeliveryStatus.id)
        self._pending_acks: Dict[str, int] = {}

        logger.info("DeliveryTracker initialized")

    def create_delivery(
        self,
        message_type: str,
        message_id: int,
        sender_key: str,
        recipient_key: Optional[str] = None,
        max_retries: Optional[int] = None,
    ) -> DeliveryStatus:
        """
        Create a new delivery status record for an outgoing message.

        Args:
            message_type: Type of message ('private', 'public', 'broadcast')
            message_id: Database ID of the message
            sender_key: Public key of the sender
            recipient_key: Public key of recipient (None for broadcasts)
            max_retries: Override default max retries

        Returns:
            The created DeliveryStatus record
        """
        session = self._session_factory()
        try:
            delivery = DeliveryStatus(
                message_type=message_type,
                message_id=message_id,
                sender_key=sender_key,
                recipient_key=recipient_key,
                state=DeliveryState.PENDING,
                max_retries=max_retries if max_retries is not None else self._default_max_retries,
            )
            session.add(delivery)
            session.commit()
            session.refresh(delivery)

            logger.debug(f"Created delivery record #{delivery.id} for {message_type}:{message_id}")
            return delivery
        finally:
            session.close()

    def mark_sending(self, delivery_id: int) -> Optional[DeliveryStatus]:
        """
        Mark a delivery as currently being sent.

        Args:
            delivery_id: ID of the delivery record

        Returns:
            Updated DeliveryStatus or None if not found
        """
        session = self._session_factory()
        try:
            delivery = session.query(DeliveryStatus).filter_by(id=delivery_id).first()
            if delivery:
                delivery.mark_sending()
                session.commit()
                session.refresh(delivery)
                logger.debug(f"Delivery #{delivery_id} marked as sending")
            return delivery
        finally:
            session.close()

    def mark_sent(
        self,
        delivery_id: int,
        external_id: Optional[str] = None,
    ) -> Optional[DeliveryStatus]:
        """
        Mark a delivery as sent (awaiting ACK).

        Args:
            delivery_id: ID of the delivery record
            external_id: MeshCore message ID for ACK correlation

        Returns:
            Updated DeliveryStatus or None if not found
        """
        session = self._session_factory()
        try:
            delivery = session.query(DeliveryStatus).filter_by(id=delivery_id).first()
            if delivery:
                delivery.mark_sent(external_id)
                session.commit()
                session.refresh(delivery)

                # Track for ACK correlation
                if external_id:
                    self._pending_acks[external_id] = delivery_id

                logger.debug(f"Delivery #{delivery_id} marked as sent (ext_id={external_id})")
            return delivery
        finally:
            session.close()

    def process_ack(
        self,
        external_id: str,
        hops: Optional[int] = None,
        rssi: Optional[int] = None,
    ) -> Optional[DeliveryStatus]:
        """
        Process an ACK received from the network.

        Args:
            external_id: MeshCore message ID from the ACK
            hops: Number of hops reported in ACK
            rssi: Signal strength reported in ACK

        Returns:
            Updated DeliveryStatus if found, None otherwise
        """
        delivery_id = self._pending_acks.pop(external_id, None)
        if delivery_id is None:
            logger.debug(f"Received ACK for unknown message: {external_id}")
            return None

        session = self._session_factory()
        try:
            delivery = session.query(DeliveryStatus).filter_by(id=delivery_id).first()
            if delivery:
                delivery.mark_delivered(hops=hops, rssi=rssi)
                session.commit()
                session.refresh(delivery)

                logger.info(f"Delivery #{delivery_id} confirmed (hops={hops}, rssi={rssi})")

                # Trigger callbacks
                for callback in self._on_delivered_callbacks:
                    try:
                        callback(delivery)
                    except Exception as e:
                        logger.error(f"Delivery callback error: {e}")

            return delivery
        finally:
            session.close()

    def mark_failed(
        self,
        delivery_id: int,
        error: str,
    ) -> Optional[DeliveryStatus]:
        """
        Mark a delivery as failed.

        Args:
            delivery_id: ID of the delivery record
            error: Error message describing the failure

        Returns:
            Updated DeliveryStatus or None if not found
        """
        session = self._session_factory()
        try:
            delivery = session.query(DeliveryStatus).filter_by(id=delivery_id).first()
            if delivery:
                delivery.mark_failed(error)
                session.commit()
                session.refresh(delivery)

                logger.warning(f"Delivery #{delivery_id} failed: {error}")

                # Trigger callbacks
                for callback in self._on_failed_callbacks:
                    try:
                        callback(delivery)
                    except Exception as e:
                        logger.error(f"Failed callback error: {e}")

            return delivery
        finally:
            session.close()

    def retry_delivery(self, delivery_id: int) -> Optional[DeliveryStatus]:
        """
        Prepare a delivery for retry.

        Args:
            delivery_id: ID of the delivery record

        Returns:
            Updated DeliveryStatus if retryable, None otherwise
        """
        session = self._session_factory()
        try:
            delivery = session.query(DeliveryStatus).filter_by(id=delivery_id).first()
            if delivery and delivery.can_retry:
                if delivery.increment_retry():
                    delivery.state = DeliveryState.PENDING
                    session.commit()
                    session.refresh(delivery)
                    logger.info(f"Delivery #{delivery_id} queued for retry ({delivery.retry_count}/{delivery.max_retries})")
                    return delivery
                else:
                    delivery.mark_failed("Max retries exceeded")
                    session.commit()
                    session.refresh(delivery)
            return delivery
        finally:
            session.close()

    def get_delivery(self, delivery_id: int) -> Optional[DeliveryStatus]:
        """
        Get a delivery status by ID.

        Args:
            delivery_id: ID of the delivery record

        Returns:
            DeliveryStatus or None if not found
        """
        session = self._session_factory()
        try:
            return session.query(DeliveryStatus).filter_by(id=delivery_id).first()
        finally:
            session.close()

    def get_delivery_by_message(
        self,
        message_type: str,
        message_id: int,
    ) -> Optional[DeliveryStatus]:
        """
        Get delivery status for a specific message.

        Args:
            message_type: Type of message
            message_id: Database ID of the message

        Returns:
            DeliveryStatus or None if not found
        """
        session = self._session_factory()
        try:
            return (
                session.query(DeliveryStatus)
                .filter_by(message_type=message_type, message_id=message_id)
                .order_by(DeliveryStatus.created_at.desc())
                .first()
            )
        finally:
            session.close()

    def get_pending_deliveries(self) -> List[DeliveryStatus]:
        """
        Get all pending delivery records.

        Returns:
            List of pending DeliveryStatus records
        """
        session = self._session_factory()
        try:
            return (
                session.query(DeliveryStatus)
                .filter(DeliveryStatus.state.in_([DeliveryState.PENDING, DeliveryState.SENDING]))
                .order_by(DeliveryStatus.created_at)
                .all()
            )
        finally:
            session.close()

    def get_stale_pending(self) -> List[DeliveryStatus]:
        """
        Get pending deliveries that have exceeded the timeout.

        Returns:
            List of stale DeliveryStatus records
        """
        session = self._session_factory()
        try:
            cutoff = datetime.utcnow() - timedelta(seconds=self._pending_timeout_seconds)
            return (
                session.query(DeliveryStatus)
                .filter(
                    DeliveryStatus.state == DeliveryState.PENDING,
                    DeliveryStatus.created_at < cutoff,
                )
                .all()
            )
        finally:
            session.close()

    def get_failed_retryable(self) -> List[DeliveryStatus]:
        """
        Get failed deliveries that can still be retried.

        Returns:
            List of retryable DeliveryStatus records
        """
        session = self._session_factory()
        try:
            return (
                session.query(DeliveryStatus)
                .filter(
                    DeliveryStatus.state == DeliveryState.FAILED,
                    DeliveryStatus.retry_count < DeliveryStatus.max_retries,
                )
                .all()
            )
        finally:
            session.close()

    def get_delivery_stats(self) -> Dict[str, int]:
        """
        Get delivery statistics.

        Returns:
            Dictionary with counts per state
        """
        session = self._session_factory()
        try:
            stats = {}
            for state in DeliveryState:
                count = (
                    session.query(DeliveryStatus)
                    .filter_by(state=state)
                    .count()
                )
                stats[state.value] = count
            return stats
        finally:
            session.close()

    def on_delivered(self, callback: Callable[[DeliveryStatus], Any]) -> None:
        """Register a callback for successful deliveries."""
        self._on_delivered_callbacks.append(callback)

    def on_failed(self, callback: Callable[[DeliveryStatus], Any]) -> None:
        """Register a callback for failed deliveries."""
        self._on_failed_callbacks.append(callback)

    def cleanup_old_records(self, days: int = 30) -> int:
        """
        Remove old delivery records.

        Args:
            days: Records older than this will be removed

        Returns:
            Number of records deleted
        """
        session = self._session_factory()
        try:
            cutoff = datetime.utcnow() - timedelta(days=days)
            deleted = (
                session.query(DeliveryStatus)
                .filter(DeliveryStatus.created_at < cutoff)
                .delete()
            )
            session.commit()
            logger.info(f"Cleaned up {deleted} old delivery records")
            return deleted
        finally:
            session.close()
