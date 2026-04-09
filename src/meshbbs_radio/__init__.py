"""MeshCore communication module."""

from .connection import (
    MeshCoreConnection,
    BLEMeshCoreConnection,
    TCPMeshCoreConnection,
    MockMeshCoreConnection,
)
from .messages import Message as MeshMessage, Advert, GroupMessage
from .protocol import PacketType
from .state import get_state_manager, MeshCoreStateManager, ConnectionStatus

__all__ = [
    "MeshCoreConnection",
    "BLEMeshCoreConnection",
    "TCPMeshCoreConnection",
    "MockMeshCoreConnection",
    "MeshMessage",
    "GroupMessage",
    "Advert",
    "PacketType",
    "get_state_manager",
    "MeshCoreStateManager",
    "ConnectionStatus",
]
