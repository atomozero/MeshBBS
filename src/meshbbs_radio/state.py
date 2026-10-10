"""
MeshCore connection state management.

MIT License - Copyright (c) 2026 MeshBBS Contributors

This module provides a global state manager for tracking the MeshCore
connection status. It allows the web interface to query the real
connection state.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Callable, List, Any

logger = logging.getLogger(__name__)


# Single-cell LiPo resting voltage (mV) -> charge (%), linear in between.
# Approximate: good enough for a dashboard gauge, not for a fuel gauge.
LIPO_CURVE = (
    (4200, 100), (4100, 90), (4000, 80), (3900, 70), (3850, 60),
    (3800, 50), (3750, 40), (3700, 30), (3650, 20), (3500, 10), (3300, 0),
)


def lipo_percent(millivolts: Optional[int]) -> Optional[int]:
    """Estimate the charge of a 1S LiPo from its voltage (3.3-4.2 V)."""
    if millivolts is None:
        return None
    try:
        mv = int(millivolts)
    except (TypeError, ValueError):
        return None
    if mv <= 0:
        return None  # no battery / not reported
    if mv >= LIPO_CURVE[0][0]:
        return 100
    if mv <= LIPO_CURVE[-1][0]:
        return 0
    for (hi_mv, hi_pct), (lo_mv, lo_pct) in zip(LIPO_CURVE, LIPO_CURVE[1:]):
        if lo_mv <= mv <= hi_mv:
            return int(round(lo_pct + (mv - lo_mv) * (hi_pct - lo_pct) / (hi_mv - lo_mv)))
    return None  # pragma: no cover


class ConnectionStatus(str, Enum):
    """Connection status states."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    ERROR = "error"


@dataclass
class RadioInfo:
    """Information about the connected radio."""

    public_key: str = ""
    name: str = ""
    port: str = ""
    baud_rate: int = 115200
    is_mock: bool = False
    battery_level: Optional[int] = None  # estimated %
    battery_charging: bool = False
    firmware_version: Optional[str] = None
    battery_mv: Optional[int] = None
    battery_updated_at: Optional[datetime] = None
    storage_used_kb: Optional[int] = None
    storage_total_kb: Optional[int] = None
    model: Optional[str] = None


@dataclass
class ConnectionState:
    """Current connection state."""

    status: ConnectionStatus = ConnectionStatus.DISCONNECTED
    radio_info: RadioInfo = field(default_factory=RadioInfo)
    connected_at: Optional[datetime] = None
    last_activity: Optional[datetime] = None
    error_message: Optional[str] = None
    message_count: int = 0
    reconnect_attempts: int = 0


class MeshCoreStateManager:
    """
    Global state manager for MeshCore connection.

    Provides a centralized way to track and query the connection
    status from anywhere in the application.
    """

    def __init__(self):
        self._state = ConnectionState()
        self._listeners: List[Callable[[ConnectionState], Any]] = []
        self._lock = asyncio.Lock()

    @property
    def state(self) -> ConnectionState:
        """Get current connection state."""
        return self._state

    @property
    def is_connected(self) -> bool:
        """Check if radio is connected."""
        return self._state.status == ConnectionStatus.CONNECTED

    @property
    def status(self) -> ConnectionStatus:
        """Get current status."""
        return self._state.status

    def add_listener(self, callback: Callable[[ConnectionState], Any]) -> None:
        """
        Add a listener for state changes.

        Args:
            callback: Function to call when state changes
        """
        self._listeners.append(callback)

    def remove_listener(self, callback: Callable[[ConnectionState], Any]) -> None:
        """
        Remove a state change listener.

        Args:
            callback: The callback to remove
        """
        if callback in self._listeners:
            self._listeners.remove(callback)

    async def _notify_listeners(self) -> None:
        """Notify all listeners of state change."""
        for listener in self._listeners:
            try:
                result = listener(self._state)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error(f"Error in state listener: {e}")

    async def set_connecting(self, port: str, baud_rate: int) -> None:
        """
        Set state to connecting.

        Args:
            port: Serial port being connected to
            baud_rate: Baud rate
        """
        async with self._lock:
            self._state.status = ConnectionStatus.CONNECTING
            self._state.radio_info.port = port
            self._state.radio_info.baud_rate = baud_rate
            self._state.error_message = None
            logger.info(f"Connection state: CONNECTING to {port}")
            await self._notify_listeners()

    async def set_connected(
        self,
        public_key: str,
        name: str,
        port: str,
        baud_rate: int = 115200,
        is_mock: bool = False,
    ) -> None:
        """
        Set state to connected.

        Args:
            public_key: Radio's public key
            name: Radio's name
            port: Serial port
            baud_rate: Baud rate
            is_mock: Whether using mock connection
        """
        async with self._lock:
            self._state.status = ConnectionStatus.CONNECTED
            self._state.radio_info = RadioInfo(
                public_key=public_key,
                name=name,
                port=port,
                baud_rate=baud_rate,
                is_mock=is_mock,
            )
            self._state.connected_at = datetime.utcnow()
            self._state.last_activity = datetime.utcnow()
            self._state.error_message = None
            self._state.reconnect_attempts = 0
            logger.info(f"Connection state: CONNECTED ({name})")
            await self._notify_listeners()

    async def set_disconnected(self, error: Optional[str] = None) -> None:
        """
        Set state to disconnected.

        Args:
            error: Optional error message
        """
        async with self._lock:
            self._state.status = ConnectionStatus.DISCONNECTED
            self._state.connected_at = None
            self._state.error_message = error
            logger.info(f"Connection state: DISCONNECTED{f' ({error})' if error else ''}")
            await self._notify_listeners()

    async def set_error(self, error: str) -> None:
        """
        Set state to error.

        Args:
            error: Error message
        """
        async with self._lock:
            self._state.status = ConnectionStatus.ERROR
            self._state.error_message = error
            logger.error(f"Connection state: ERROR - {error}")
            await self._notify_listeners()

    async def set_reconnecting(self, attempt: int) -> None:
        """
        Set state to reconnecting.

        Args:
            attempt: Current reconnection attempt number
        """
        async with self._lock:
            self._state.status = ConnectionStatus.RECONNECTING
            self._state.reconnect_attempts = attempt
            logger.info(f"Connection state: RECONNECTING (attempt {attempt})")
            await self._notify_listeners()

    async def update_activity(self) -> None:
        """Update last activity timestamp."""
        async with self._lock:
            self._state.last_activity = datetime.utcnow()
            self._state.message_count += 1

    async def update_battery(
        self,
        millivolts: Optional[int],
        used_kb: Optional[int] = None,
        total_kb: Optional[int] = None,
    ) -> None:
        """
        Update battery information from the companion BATTERY reply.

        Args:
            millivolts: Battery voltage in mV (meshcore payload 'level')
            used_kb: Storage used (KB), if reported
            total_kb: Storage total (KB), if reported
        """
        async with self._lock:
            info = self._state.radio_info
            try:
                mv = int(millivolts) if millivolts is not None else None
            except (TypeError, ValueError):
                mv = None
            info.battery_mv = mv if mv and mv > 0 else None
            info.battery_level = lipo_percent(info.battery_mv)
            info.battery_updated_at = datetime.utcnow()
            if used_kb is not None:
                info.storage_used_kb = used_kb
            if total_kb is not None:
                info.storage_total_kb = total_kb

    async def update_device_info(self, model: Optional[str], firmware: Optional[str]) -> None:
        """Store companion model / firmware version (from the device query)."""
        async with self._lock:
            if model:
                self._state.radio_info.model = model
            if firmware:
                self._state.radio_info.firmware_version = firmware

    def to_dict(self) -> dict:
        """
        Convert current state to dictionary.

        Returns:
            Dictionary representation of the state
        """
        state = self._state
        return {
            "status": state.status.value,
            "is_connected": self.is_connected,
            "radio": {
                "public_key": state.radio_info.public_key,
                "name": state.radio_info.name,
                "port": state.radio_info.port,
                "baud_rate": state.radio_info.baud_rate,
                "is_mock": state.radio_info.is_mock,
                "battery_level": state.radio_info.battery_level,
                "battery_charging": state.radio_info.battery_charging,
                "battery_mv": state.radio_info.battery_mv,
                "model": state.radio_info.model,
                "firmware_version": state.radio_info.firmware_version,
            } if self.is_connected else None,
            "connected_at": state.connected_at.isoformat() if state.connected_at else None,
            "last_activity": state.last_activity.isoformat() if state.last_activity else None,
            "error": state.error_message,
            "message_count": state.message_count,
            "reconnect_attempts": state.reconnect_attempts,
        }


# Global singleton instance
_state_manager: Optional[MeshCoreStateManager] = None


def get_state_manager() -> MeshCoreStateManager:
    """
    Get the global MeshCore state manager.

    Returns:
        The singleton MeshCoreStateManager instance
    """
    global _state_manager
    if _state_manager is None:
        _state_manager = MeshCoreStateManager()
    return _state_manager


def reset_state_manager() -> None:
    """Reset the global state manager (mainly for testing)."""
    global _state_manager
    _state_manager = None
