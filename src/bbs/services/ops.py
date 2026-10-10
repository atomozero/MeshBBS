"""
Operational background services of a running BBS.

MIT License - Copyright (c) 2026 MeshBBS Contributors

Groups what keeps the node healthy without being BBS logic, so BBSCore
only needs start/stop/on_message:
- MQTT bridge (optional, MQTT_ENABLED=true)
- nightly database backup (BACKUP_ENABLED, default on)
- hourly WAL checkpoint (keeps the -wal file small on the SD card)
"""

import asyncio
from typing import Any, List, Optional

from bbs.models.sqlite_tuning import periodic_checkpoint
from bbs.services.backup import nightly_backup_loop
from bbs.services.mqtt_bridge import MQTTBridge, start_mqtt_bridge

try:
    from utils.logger import get_logger
    logger = get_logger("meshbbs.ops")
except ImportError:  # pragma: no cover
    import logging
    logger = logging.getLogger("meshbbs.ops")


class OpsServices:
    def __init__(self) -> None:
        self.mqtt: Optional[MQTTBridge] = None
        self._tasks: List[asyncio.Task] = []

    async def start(self, bbs: Any) -> None:
        db_path = bbs.config.database_path
        self._tasks.append(asyncio.create_task(nightly_backup_loop(db_path), name="backup"))
        self._tasks.append(asyncio.create_task(periodic_checkpoint(), name="wal-checkpoint"))
        self.mqtt = await start_mqtt_bridge(bbs)

    async def stop(self) -> None:
        for task in self._tasks:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
        self._tasks.clear()
        if self.mqtt is not None:
            try:
                await self.mqtt.stop()
            except Exception as e:
                logger.debug(f"MQTT stop error: {e}")
            self.mqtt = None

    def on_message(self, message: Any) -> None:
        """Incoming radio message (never raises)."""
        if self.mqtt is not None:
            try:
                self.mqtt.on_incoming_message(message)
            except Exception as e:
                logger.debug(f"MQTT message event failed: {e}")


async def start_ops_services(bbs: Any) -> OpsServices:
    ops = OpsServices()
    try:
        await ops.start(bbs)
    except Exception as e:
        logger.error(f"Ops services start error: {e}")
    return ops
