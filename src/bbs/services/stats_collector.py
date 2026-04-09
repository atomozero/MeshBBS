"""
Statistics collector service for MeshCore BBS.

Collects and aggregates BBS usage metrics into a unified payload
suitable for both REST API consumption and MQTT publishing.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

import os
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import func

from bbs.models.user import User
from bbs.models.message import Message
from bbs.models.area import Area
from bbs.models.private_message import PrivateMessage
from bbs.models.activity_log import ActivityLog, EventType
from meshbbs_radio.state import get_state_manager

try:
    from utils.logger import get_logger
    logger = get_logger("meshbbs.stats")
except ImportError:
    import logging
    logger = logging.getLogger("meshbbs.stats")


class StatsCollector:
    """
    Collects and aggregates BBS usage statistics.

    Produces a single dict payload consumed by both the REST API
    endpoint and the MQTT periodic publisher.
    """

    def __init__(self, session: Session):
        self._session = session

    def collect(self) -> Dict[str, Any]:
        """
        Collect all statistics and return a unified payload.

        Returns:
            Dictionary with users, messages, radio, delivery, and system sections.
        """
        now = datetime.utcnow()

        return {
            "users": self._collect_users(now),
            "messages": self._collect_messages(now),
            "radio": self._collect_radio(),
            "delivery": self._collect_delivery(),
            "system": self._collect_system(),
            "collected_at": now.isoformat(),
        }

    # ------------------------------------------------------------------
    # Users
    # ------------------------------------------------------------------

    def _collect_users(self, now: datetime) -> Dict[str, Any]:
        db = self._session
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        total = db.query(User).count()
        active_24h = db.query(User).filter(
            User.last_seen >= now - timedelta(hours=24)
        ).count()
        active_7d = db.query(User).filter(
            User.last_seen >= now - timedelta(days=7)
        ).count()

        # New users today
        new_today = db.query(User).filter(
            User.first_seen >= today_start
        ).count()

        return {
            "total": total,
            "active_24h": active_24h,
            "active_7d": active_7d,
            "new_today": new_today,
            "banned": db.query(User).filter(User.is_banned == True).count(),
            "muted": db.query(User).filter(User.is_muted == True).count(),
        }

    # ------------------------------------------------------------------
    # Messages
    # ------------------------------------------------------------------

    def _collect_messages(self, now: datetime) -> Dict[str, Any]:
        db = self._session
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        hour_ago = now - timedelta(hours=1)

        total = db.query(Message).count()
        today = db.query(Message).filter(Message.timestamp >= today_start).count()
        last_hour = db.query(Message).filter(Message.timestamp >= hour_ago).count()
        week = db.query(Message).filter(
            Message.timestamp >= now - timedelta(days=7)
        ).count()

        # Private messages
        pm_total = db.query(PrivateMessage).count()
        pm_today = db.query(PrivateMessage).filter(
            PrivateMessage.timestamp >= today_start
        ).count()
        pm_unread = db.query(PrivateMessage).filter(
            PrivateMessage.is_read == False
        ).count()

        # Areas
        total_areas = db.query(Area).count()

        return {
            "public": {
                "total": total,
                "today": today,
                "last_hour": last_hour,
                "week": week,
            },
            "private": {
                "total": pm_total,
                "today": pm_today,
                "unread": pm_unread,
            },
            "areas": total_areas,
        }

    # ------------------------------------------------------------------
    # Radio / Connection
    # ------------------------------------------------------------------

    def _collect_radio(self) -> Dict[str, Any]:
        state_manager = get_state_manager()
        state = state_manager.state

        data: Dict[str, Any] = {
            "status": state.status.value,
            "connected": state_manager.is_connected,
            "messages_processed": state.message_count,
            "reconnect_attempts": state.reconnect_attempts,
        }

        if state_manager.is_connected:
            data["name"] = state.radio_info.name
            data["port"] = state.radio_info.port
            data["battery_level"] = state.radio_info.battery_level
            data["battery_charging"] = state.radio_info.battery_charging

            if state.connected_at:
                uptime = (datetime.utcnow() - state.connected_at).total_seconds()
                data["uptime_seconds"] = int(uptime)

        if state.last_activity:
            data["last_activity"] = state.last_activity.isoformat()

        return data

    # ------------------------------------------------------------------
    # Delivery
    # ------------------------------------------------------------------

    def _collect_delivery(self) -> Dict[str, Any]:
        """Collect delivery statistics if the delivery_status table exists."""
        try:
            from bbs.models.delivery_status import DeliveryStatus, DeliveryState

            stats: Dict[str, int] = {}
            for ds in DeliveryState:
                count = (
                    self._session.query(DeliveryStatus)
                    .filter_by(state=ds)
                    .count()
                )
                stats[ds.value] = count

            total = sum(stats.values())
            delivered = stats.get("delivered", 0) + stats.get("read", 0)
            failed = stats.get("failed", 0)

            return {
                "by_state": stats,
                "total": total,
                "success_rate": round(delivered / total * 100, 1) if total > 0 else 0.0,
                "failed": failed,
            }

        except Exception:
            return {"available": False}

    # ------------------------------------------------------------------
    # System
    # ------------------------------------------------------------------

    def _collect_system(self) -> Dict[str, Any]:
        from utils.config import get_config
        config = get_config()

        # DB size
        db_size = 0
        if os.path.exists(config.database_path):
            db_size = os.path.getsize(config.database_path)

        # Process uptime
        uptime = int(time.time() - time.monotonic())

        # Memory (Linux only)
        memory: Optional[Dict[str, int]] = None
        try:
            with open("/proc/meminfo") as f:
                meminfo = f.read()
            for line in meminfo.splitlines():
                if line.startswith("MemAvailable"):
                    mem_avail = int(line.split()[1]) * 1024
                elif line.startswith("MemTotal"):
                    mem_total = int(line.split()[1]) * 1024
            memory = {"available": mem_avail, "total": mem_total}
        except Exception:
            pass

        data: Dict[str, Any] = {
            "bbs_name": config.bbs_name,
            "uptime_seconds": uptime,
            "db_size_bytes": db_size,
        }
        if memory:
            data["memory"] = memory

        return data
